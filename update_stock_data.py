# -*- coding: utf-8 -*-
"""
增量更新沪深300股票数据
修复 baostock adapter 的 pandas.append 兼容性问题
"""
import os
import sys
import time
import pandas as pd
import baostock as bs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
STOCK_DATA_PATH = os.path.join(DATA_DIR, 'stock_data.csv')
HS300_LIST_PATH = os.path.join(DATA_DIR, 'hs300_stock_list.csv')

START_DATE_DEFAULT = '2015-01-01'
END_DATE_DEFAULT = '2026-08-01'
ADJUST_FLAG = '1'  # 后复权


def login_baostock():
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f'baostock login failed: {lg.error_msg}')
    print('[baostock] 登录成功')


def logout_baostock():
    bs.logout()
    print('[baostock] 已登出')


def get_hs300_symbols(as_of_date=''):
    """获取沪深300成分股列表"""
    print(f'[hs300] 查询成分股列表 (as_of={as_of_date or "最新"})...')
    result = bs.query_hs300_stocks(as_of_date or '')
    if result.error_code != '0':
        raise RuntimeError(f'query hs300 failed: {result.error_msg}')
    df = result.get_data()
    symbols = df['code'].dropna().astype(str).tolist()
    names = df['code_name'].dropna().astype(str).tolist() if 'code_name' in df.columns else symbols
    print(f'[hs300] 获取到 {len(symbols)} 只成分股')
    return symbols, names


def fetch_one_stock(symbol, start_date, end_date):
    """下载单只股票数据，返回DataFrame"""
    fields = 'date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,tradestatus'
    rs = bs.query_history_k_data_plus(
        symbol,
        fields,
        start_date=start_date,
        end_date=end_date,
        frequency='d',
        adjustflag=ADJUST_FLAG,
    )
    if rs.error_code != '0':
        raise RuntimeError(f'fetch {symbol} failed: {rs.error_msg}')
    data_list = []
    while (rs.error_code == '0') and rs.next():
        data_list.append(rs.get_row_data())
    if not data_list:
        return pd.DataFrame(columns=fields.split(','))
    df = pd.DataFrame(data_list, columns=fields.split(','))
    return df


def num_to_code(x):
    x = str(x).strip()
    digits = ''.join(c for c in x if c.isdigit())
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6) if digits else x


def load_existing_stock_data():
    """加载现有stock_data.csv，返回(stock_code->date_set, 完整df)"""
    if not os.path.exists(STOCK_DATA_PATH):
        return {}, pd.DataFrame()
    print(f'[data] 读取已有数据: {STOCK_DATA_PATH}')
    df = pd.read_csv(STOCK_DATA_PATH, dtype=str)
    df['股票代码'] = df['股票代码'].apply(num_to_code)
    df['_date_ts'] = pd.to_datetime(df['日期'], errors='coerce')
    stock_dates = {}
    for code, sub in df.groupby('股票代码'):
        stock_dates[str(code)] = set(sub['_date_ts'].dropna().dt.strftime('%Y-%m-%d').tolist())
    df = df.drop(columns=['_date_ts'])
    print(f'[data] 已有 {len(df)} 行, 股票数={len(stock_dates)}, '
          f'日期范围={df["日期"].min()} ~ {df["日期"].max()}')
    return stock_dates, df


def convert_baostock_to_local(raw, stock_code):
    """把baostock返回的字段映射为stock_data.csv格式"""
    if raw.empty:
        return pd.DataFrame()
    # 数字列转换
    numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn', 'pctChg']
    for col in numeric_cols:
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors='coerce')
    # 映射列名
    # baostock: date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,tradestatus
    out = pd.DataFrame()
    out['股票代码'] = [stock_code] * len(raw)
    out['日期'] = pd.to_datetime(raw['date'], errors='coerce').dt.strftime('%Y/%m/%d')
    out['开盘'] = raw['open'].values
    out['收盘'] = raw['close'].values
    out['最高'] = raw['high'].values
    out['最低'] = raw['low'].values
    out['成交量'] = raw['volume'].values
    out['成交额'] = raw['amount'].values
    # 振幅 = (最高-最低)/preclose
    preclose = pd.to_numeric(raw['preclose'], errors='coerce')
    high = pd.to_numeric(raw['high'], errors='coerce')
    low = pd.to_numeric(raw['low'], errors='coerce')
    out['振幅'] = ((high - low) / preclose * 100).round(4).values
    # 涨跌额 = 收盘-preclose
    close = pd.to_numeric(raw['close'], errors='coerce')
    out['涨跌额'] = (close - preclose).round(4).values
    out['换手率'] = pd.to_numeric(raw['turn'], errors='coerce').round(4).values
    out['涨跌幅'] = pd.to_numeric(raw['pctChg'], errors='coerce').round(4).values
    out = out.dropna(subset=['日期'])
    return out


def parse_dates(args):
    start = args[1] if len(args) > 1 else START_DATE_DEFAULT
    end = args[2] if len(args) > 2 else END_DATE_DEFAULT
    return start, end


def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ('-h', '--help'):
        print('用法: python update_stock_data.py [起始日期 YYYY-MM-DD] [结束日期 YYYY-MM-DD]')
        print(f'默认: {START_DATE_DEFAULT} ~ {END_DATE_DEFAULT}')
        return
    start_date, end_date = parse_dates(sys.argv)
    print(f'========================================')
    print(f'  沪深300数据增量更新')
    print(f'  日期范围: {start_date} ~ {end_date}')
    print(f'========================================')

    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. 读取现有数据日期范围（加速）
    existing_stock_dates, existing_df = load_existing_stock_data()

    # 2. 获取沪深300成分股
    login_baostock()
    try:
        symbols, names = get_hs300_symbols()
    except Exception as e:
        print(f'获取最新hs300失败，尝试用历史列表: {e}')
        if os.path.exists(HS300_LIST_PATH):
            list_df = pd.read_csv(HS300_LIST_PATH, dtype=str)
            if 'code' in list_df.columns:
                symbols = list_df['code'].dropna().astype(str).tolist()
                names = list_df['code_name'].dropna().astype(str).tolist() if 'code_name' in list_df.columns else symbols
                print(f'[hs300] 使用历史列表, 共{len(symbols)}只')
            else:
                raise
        else:
            raise
    # 保存成分股列表
    list_df = pd.DataFrame({'code': symbols, 'code_name': names})
    list_df.to_csv(HS300_LIST_PATH, index=False, encoding='utf-8-sig')

    # 3. 逐只下载（增量）
    all_new_rows = []
    skipped = 0
    updated = 0
    for i, symbol in enumerate(symbols):
        stock_code = num_to_code(symbol)
        # 判断每只股票已有日期，只取缺失的
        existing_dates = existing_stock_dates.get(stock_code, set())
        need = True
        if existing_dates:
            # 用end_date粗略估计，如果end_date日期已经有了，就跳过（严格版可以用日期范围）
            if end_date.replace('-', '/') in set(d.replace('-', '/') for d in existing_dates):
                skipped += 1
                need = False
        if not need:
            print(f'  [{i+1}/{len(symbols)}] {symbol} {stock_code} → 已完整，跳过')
            continue
        # 下载（可以全区间下载，最后去重合并；或者增量取min(max+1, start)~end）
        eff_start = start_date
        if existing_dates:
            try:
                max_dt = max(pd.to_datetime(list(existing_dates)))
                max_next = (max_dt + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                eff_start = max(pd.to_datetime(start_date), pd.to_datetime(max_next)).strftime('%Y-%m-%d')
            except Exception:
                pass
        try:
            raw = fetch_one_stock(symbol, eff_start, end_date)
            if not raw.empty:
                converted = convert_baostock_to_local(raw, stock_code)
                if not converted.empty:
                    all_new_rows.append(converted)
                    updated += 1
                    print(f'  [{i+1}/{len(symbols)}] {symbol} {stock_code} → 新增 {len(converted)} 行')
                else:
                    print(f'  [{i+1}/{len(symbols)}] {symbol} {stock_code} → 无新数据')
            else:
                print(f'  [{i+1}/{len(symbols)}] {symbol} {stock_code} → 无数据')
        except Exception as e:
            print(f'  [{i+1}/{len(symbols)}] {symbol} {stock_code} → 失败: {e}')
        # 限速
        if (i + 1) % 10 == 0:
            time.sleep(2)
    logout_baostock()

    # 4. 合并旧数据和新数据，按股票相邻+日期排序
    if all_new_rows:
        new_df = pd.concat(all_new_rows, ignore_index=True)
        print(f'\n[merge] 下载完成: 新增{len(new_df)}行, 旧{len(existing_df)}行')
        if not existing_df.empty:
            # 统一日期格式为 %Y/%m/%d
            new_df['日期'] = pd.to_datetime(new_df['日期'], errors='coerce').dt.strftime('%Y/%m/%d')
            existing_df['日期'] = pd.to_datetime(existing_df['日期'], errors='coerce').dt.strftime('%Y/%m/%d')
            merged = pd.concat([existing_df, new_df], ignore_index=True)
            # 股票代码标准化后去重
            merged['股票代码'] = merged['股票代码'].apply(num_to_code)
            merged = merged.drop_duplicates(subset=['股票代码', '日期'], keep='last')
            # 按(股票代码, 日期)排序，保证同股票相邻
            merged = merged.sort_values(by=['股票代码', '日期']).reset_index(drop=True)
        else:
            merged = new_df.sort_values(by=['股票代码', '日期']).reset_index(drop=True)
        # 保存
        merged.to_csv(STOCK_DATA_PATH, index=False, encoding='utf-8-sig')
        print(f'[save] 已写入 {STOCK_DATA_PATH}, 共{len(merged)}行')
        print(f'[save] 日期范围: {merged["日期"].min()} ~ {merged["日期"].max()}')
    else:
        print('\n[merge] 没有任何新增数据，无需保存')

    # 5. 计算MD5
    try:
        import hashlib
        with open(STOCK_DATA_PATH, 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        print(f'[MD5] {STOCK_DATA_PATH}: {md5.upper()}')
    except Exception as e:
        print(f'[MD5] 计算失败: {e}')

    print('\n========================================')
    print(f'  全部完成 (更新{updated}只，跳过{skipped}只)')
    print(f'========================================')


if __name__ == '__main__':
    main()
