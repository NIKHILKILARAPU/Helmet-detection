# Training & Evaluation Datasets

This directory is reserved for training, validation, and benchmarking datasets (e.g., Roboflow helmet detection datasets, OpenImages rider subsets, annotated traffic camera frames).

## Suggested Structure (YOLO Format)
```text
datasets/
├── images/
│   ├── train/
│   └── val/
└── labels/
    ├── train/
    └── val/
```

## Classes
Standard class mappings:
- `0: with_helmet`
- `1: without_helmet`
- `2: motorcycle`
- `3: license_plate`

> **Note**: Datasets are kept strictly outside `frontend/` and excluded from Git via `.gitignore` to maintain lightweight repository clones on Dell Latitude 5300 (8GB RAM).
