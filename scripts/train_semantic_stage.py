import argparse
import os
import sys
from pathlib import Path

import torch

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from open_musiclm.config import (create_clap_quantized_from_config,
                                 create_encodec_from_config,
                                 create_hubert_kmeans_from_config,
                                 create_semantic_transformer_from_config,
                                 create_single_stage_trainer_from_config,
                                 load_model_config, load_training_config)
from scripts.train_utils import disable_print, get_latest_checkpoints

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='train semantic stage')
    parser.add_argument('--results_folder', default='./results/semantic')
    parser.add_argument('--continue_from_dir', default=None, type=str)
    parser.add_argument('--continue_from_step', default=None, type=int)
    parser.add_argument('--model_config', default='./configs/model/musiclm_small.json')
    parser.add_argument('--training_config', default='./configs/training/train_musiclm_fma.json')
    parser.add_argument('--rvq_path', default='./checkpoints/clap.rvq.350.pt')
    parser.add_argument('--kmeans_path', default='./results/hubert_kmeans/kmeans.joblib')

    args = parser.parse_args()

    print(f'saving results to {args.results_folder}, using model config {args.model_config} and training config {args.training_config}, using rvq checkpoint {args.rvq_path} and kmeans checkpoint {args.kmeans_path}')
    if args.continue_from_dir is not None:
        print(f'continuing from latest checkpoint in {args.continue_from_dir}')
        assert not Path(args.continue_from_dir) == Path(args.results_folder), 'continue_from_dir must be different from results_folder'

    model_config = load_model_config(args.model_config)
    training_config = load_training_config(args.training_config)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    use_preprocessed_data = training_config.semantic_trainer_cfg.use_preprocessed_data

    if use_preprocessed_data:
        clap = None
        wav2vec = None
        print(f'training from preprocessed data {training_config.semantic_trainer_cfg.folder}')
    else:
        print('loading clap...')
        clap = create_clap_quantized_from_config(model_config, args.rvq_path, device)

        print('loading wav2vec...')
        wav2vec = create_hubert_kmeans_from_config(model_config, args.kmeans_path, device)

    print('loading semantic stage...')
    semantic_transformer = create_semantic_transformer_from_config(model_config, None, device)

    trainer = create_single_stage_trainer_from_config(
        model_config=model_config, 
        training_config=training_config,
        stage='semantic',
        results_folder=args.results_folder, 
        transformer=semantic_transformer,
        clap=clap,
        wav2vec=wav2vec,
        encodec_wrapper=None,
        device=device,
        accelerate_kwargs={
            'log_with': "tensorboard",
            'logging_dir': './logs/semantic'
        },
        config_paths=[args.model_config, args.training_config])

    if args.continue_from_dir is not None:
        checkpoints, steps = get_latest_checkpoints(args.continue_from_dir, args.continue_from_step)
        print(f'loading checkpoints: {checkpoints}')
        trainer.load(*checkpoints, steps=steps+1)

    trainer.train()
