import os
import sys
import json
import argparse
import subprocess
import shutil


def main():
    parser = argparse.ArgumentParser(description='多种子模型训练')
    parser.add_argument('--seeds', nargs='+', type=int, default=[42, 123, 456],
                        help='随机种子列表，默认: 42 123 456')
    parser.add_argument('--base-output-dir', type=str, default='./model',
                        help='基础输出目录')
    parser.add_argument('--config-override', type=str, default='',
                        help='配置覆盖JSON文件路径')
    args = parser.parse_args()

    current_script_path = os.path.abspath(__file__)
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))
    train_script = os.path.join(os.path.dirname(current_script_path), 'train.py')

    print(f'项目目录: {project_dir}')
    print(f'训练脚本: {train_script}')
    print(f'种子列表: {args.seeds}')
    print(f'模型数量: {len(args.seeds)}')

    for i, seed in enumerate(args.seeds):
        print(f'\n{"="*60}')
        print(f'训练模型 {i+1}/{len(args.seeds)}: seed={seed}')
        print(f'{"="*60}')

        output_dir = os.path.join(project_dir, 'model', f'60_158+39_seed{seed}')

        override_config = {
            'seed': seed,
            'output_dir': output_dir,
        }

        if args.config_override and os.path.exists(args.config_override):
            with open(args.config_override, 'r', encoding='utf-8') as f:
                extra_config = json.load(f)
            override_config.update(extra_config)

        override_path = os.path.join(project_dir, f'temp_override_seed{seed}.json')
        with open(override_path, 'w', encoding='utf-8') as f:
            json.dump(override_config, f, ensure_ascii=False, indent=2)

        env = os.environ.copy()
        env['THU_BDC_CONFIG_OVERRIDE_PATH'] = override_path

        cmd = [
            sys.executable,
            train_script,
        ]

        print(f'输出目录: {output_dir}')
        print(f'执行命令: {" ".join(cmd)}')

        try:
            result = subprocess.run(
                cmd,
                cwd=project_dir,
                env=env,
                capture_output=False,
                text=True,
            )
            if result.returncode != 0:
                print(f'警告: 模型 seed={seed} 训练失败，返回码: {result.returncode}')
            else:
                print(f'模型 seed={seed} 训练完成')
        except Exception as e:
            print(f'错误: 模型 seed={seed} 训练异常: {e}')
        finally:
            if os.path.exists(override_path):
                try:
                    os.remove(override_path)
                except:
                    pass

    print(f'\n{"="*60}')
    print('所有模型训练完成')
    print(f'{"="*60}')
    print(f'模型输出目录:')
    for seed in args.seeds:
        output_dir = os.path.join(project_dir, 'model', f'60_158+39_seed{seed}')
        model_path = os.path.join(output_dir, 'best_model.pth')
        status = '✓ 完成' if os.path.exists(model_path) else '✗ 失败'
        print(f'  seed={seed}: {output_dir} {status}')


if __name__ == '__main__':
    main()
