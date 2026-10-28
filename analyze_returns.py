import pandas as pd

test_data = pd.read_csv('data/test.csv')
test_data = test_data[['股票代码', '日期', '开盘']]
test_data['股票代码'] = test_data['股票代码'].astype(str).str.zfill(6)

def calc_ret(group):
    return (group.iloc[-1]['开盘'] - group.iloc[0]['开盘']) / group.iloc[0]['开盘']

returns = test_data.groupby('股票代码').apply(calc_ret).reset_index()
returns.columns = ['股票代码', '收益率']
returns = returns.sort_values('收益率', ascending=False).reset_index(drop=True)

print('收益率最高的10只股票：')
for i in range(10):
    code = returns.iloc[i]['股票代码']
    ret = returns.iloc[i]['收益率']
    print(f'  {i+1}. {code}: {ret:.4f} ({ret*100:.2f}%)')

print()
print('前5只等权收益率:', returns.head(5)['收益率'].mean())
print('前4只等权收益率:', returns.head(4)['收益率'].mean())
print('前3只等权收益率:', returns.head(3)['收益率'].mean())
print('前2只等权收益率:', returns.head(2)['收益率'].mean())

our_stocks = ['601360', '688981', '300059', '688472', '300274']
our_returns = returns[returns['股票代码'].isin(our_stocks)]
print()
print('我们选的5只股票排名：')
for _, row in our_returns.iterrows():
    rank = returns[returns['收益率'] >= row['收益率']].index[0] + 1
    print(f'  {row["股票代码"]}: 排名{rank}, 收益率{row["收益率"]*100:.2f}%')
print(f'  平均收益率: {our_returns["收益率"].mean()*100:.2f}%')
