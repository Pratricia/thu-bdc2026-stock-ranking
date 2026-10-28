"""
测试/推理脚本
==============

加载训练好的模型，对测试数据进行预测，输出选股结果。

输出文件:
- output/result.csv: 最终选股结果（stock_id, weight）
- output/prediction_scores.csv: 所有股票的预测分数
"""

import os
import sys
import random
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def set_seed(seed=42):
    """固定随机种子，确保可复现"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)


if __name__ == '__main__':
    from config import config
    
    seed = config.get('seed', 42)
    set_seed(seed)
    print(f'[test.py] 固定随机种子: {seed}')
    
    from predict import main
    main()
