# Copyright 2024 Vadym Gryshchuk (vadym.gryshchuk@protonmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This script generates the results of the benchmark experiments.
Run it with ``poetry run python generate_results.py --project_path=path``
The project_path should point to the files generated by ``benchmark.py``
The generated results are saved to a log_results.log file.
"""
import argparse
import glob
import logging
import os

import pandas as pd
import torch.nn
from torch import tensor
from torchmetrics.classification import BinaryCohenKappa, BinaryPrecision, \
    BinaryRecall, BinaryMatthewsCorrCoef, BinaryAUROC

from src.misc.utils import set_logging, set_seed, create_args


def run(file_pattern: str, args: argparse.Namespace):
    # Read predictions:
    filepaths = glob.glob(
        os.path.join(args.project_path, file_pattern))
    if not filepaths:
        logging.warning('No files found. Quitting...')
        return
    results = []
    for fp in filepaths:
        with open(fp, 'r') as f:
            logging.info('Reading %s', fp)
            results.append(pd.read_pickle(f.name))
    results = pd.concat(results)

    # Apply sigmoid to predictions based on the model type:
    mask = (results['model'].isin(['eegnet', 'lstm', 'uercm']))
    masked_results = results.loc[mask]
    results.loc[mask, 'predictions'] = masked_results['predictions'].apply(
        lambda x: torch.nn.Sigmoid()(torch.FloatTensor([x])).tolist().pop())

    # Calculate classification metrics:
    groups = results.groupby(
        ['seed', 'user', 'model', 'strategy', 'reading_task'])
    mcc = groups.apply(
        lambda x: BinaryMatthewsCorrCoef()(tensor(x.predictions.tolist()),
                                           tensor(x.targets.tolist())).item(),
        include_groups=False).reset_index()
    mcc.rename(columns={0: 'mcc'}, inplace=True)
    kappa = groups.apply(
        lambda x: BinaryCohenKappa()(tensor(x.predictions.tolist()),
                                     tensor(x.targets.tolist())).item(),
        include_groups=False).reset_index()
    kappa.rename(columns={0: 'kappa'}, inplace=True)

    precision = groups.apply(
        lambda x: BinaryPrecision()(tensor(x.predictions.tolist()),
                                    tensor(x.targets.tolist())).item(),
        include_groups=False).reset_index()
    precision.rename(columns={0: 'precision'}, inplace=True)

    recall = groups.apply(
        lambda x: BinaryRecall()(tensor(x.predictions.tolist()),
                                 tensor(x.targets.tolist())).item(),
        include_groups=False).reset_index()
    recall.rename(columns={0: 'recall'}, inplace=True)

    auc = groups.apply(
        lambda x: BinaryAUROC()(tensor(x.predictions.tolist()),
                                tensor(x.targets.tolist())).item(),
        include_groups=False).reset_index()
    auc.rename(columns={0: 'auc'}, inplace=True)

    # Concatenate metrics:
    metrics = mcc.merge(precision, on=['seed', 'user', 'model', 'strategy',
                                       'reading_task'])
    metrics = metrics.merge(kappa, on=['seed', 'user', 'model', 'strategy',
                                       'reading_task'])
    metrics = metrics.merge(recall, on=['seed', 'user', 'model', 'strategy',
                                        'reading_task'])
    metrics = metrics.merge(auc, on=['seed', 'user', 'model', 'strategy',
                                     'reading_task'])

    for model in metrics.model.unique():
        latex_output = ''
        for strategy in metrics.strategy.unique()[::-1]:
            logging.info('\n\nModel: %s, Strategy: %s', model, strategy)
            for metric in ['auc', 'precision', 'recall']:
                mean = metrics[(metrics['model'] == model) & (
                        metrics['strategy'] == strategy)][
                    metric].mean()
                std = metrics[(metrics['model'] == model) & (
                        metrics['strategy'] == strategy)][
                    metric].std()
                logging.info('%s: %.2f +- %.2f', metric, mean, std)
                latex_output += f'& {mean:.2f} ({std:.2f}) '

        logging.info(latex_output)


if __name__ == '__main__':
    parser = create_args(seeds_args=False, benchmark_args=False)
    args = parser.parse_args()

    set_logging(args.project_path, file_name='logs_results')
    set_seed(1)
    logging.info('Args: %s', args)

    logging.info('Generating results for word relevance...')
    run(file_pattern='w_relevance_seed*.pkl', args=args)

    logging.info('Generating results for sentence relevance...')
    run(file_pattern='s_relevance_seed*.pkl', args=args)
