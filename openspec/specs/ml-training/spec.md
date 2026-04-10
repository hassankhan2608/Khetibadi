# ML Training Specification

## Purpose

Datasets, download instructions, training procedures, evaluation metrics, and model persistence for all three ML services. This spec is the definitive reference for reproducing trained models.

## Requirements

### Requirement: Crop Recommendation Dataset

The system SHALL use the Kaggle crop recommendation dataset (Atharva Ingle, 2200 rows) as the training source for the crop recommendation model.

#### Scenario: Dataset access
- **Name**: Crop Recommendation Dataset
- **Source**: https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset
- **File**: `Crop_recommendation.csv`
- **Rows**: 2200
- **Features**: N, P, K, temperature, humidity, ph, rainfall
- **Target**: `label` (22 crop classes)
- **License**: CC0 Public Domain

#### Scenario: Download procedure
```bash
pip install kaggle
kaggle datasets download -d atharvaingle/crop-recommendation-dataset -p data/crop/
unzip data/crop/crop-recommendation-dataset.zip -d data/crop/
```

#### Scenario: Class balance
- WHEN the dataset is loaded
- THEN each of the 22 classes has exactly 100 samples
- AND no oversampling or SMOTE is needed

---

### Requirement: Crop Recommendation Model Training

The system SHALL train a Random Forest Classifier with the following configuration.

#### Scenario: Training script
```python
# apps/ml-crop/scripts/train_crop.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import joblib

df = pd.read_csv("data/crop/Crop_recommendation.csv")
X = df[["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]]
y = df["label"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

model = RandomForestClassifier(n_estimators=100, max_depth=None, random_state=42, n_jobs=-1)
model.fit(X_train_s, y_train)

acc = accuracy_score(y_test, model.predict(X_test_s))
cv  = cross_val_score(model, X_train_s, y_train, cv=5).mean()

print(f"Test accuracy:  {acc:.4f}")   # expected: ~0.98
print(f"CV accuracy:    {cv:.4f}")    # expected: ~0.97

joblib.dump({"model": model, "scaler": scaler, "features": list(X.columns)},
            "apps/ml-crop/models/crop_model.pkl")
```

#### Scenario: Expected metrics
- Test accuracy: ≥ 0.97
- 5-fold CV accuracy: ≥ 0.96
- Per-class precision and recall: ≥ 0.90 for all 22 classes

---

### Requirement: Yield Prediction Dataset

The system SHALL use the Government of India crop production dataset for yield model training.

#### Scenario: Dataset access
- **Name**: India Crop Production Statistics (1997–2020)
- **Source**: https://www.kaggle.com/datasets/pyatakov/india-agriculture-crop-production
- **Alternative source**: https://data.gov.in/resource/crop-wise-production
- **File**: `crop_production.csv`
- **Rows**: ~1.5 million
- **Features**: State_Name, District_Name, Crop_Year, Season, Crop, Area (hectares), Production (tonnes)
- **Target**: Derived column `yield_t_ha = Production / Area`

#### Scenario: Preprocessing
```python
df = df.dropna(subset=["Production", "Area"])
df = df[df["Area"] > 0]
df["yield_t_ha"] = df["Production"] / df["Area"]
df = df[df["yield_t_ha"] < 100]  # remove outliers > 100 t/ha
```

---

### Requirement: Yield Prediction Model Training

The system SHALL train a Gradient Boosting Regressor for yield prediction.

#### Scenario: Training script key parameters
```python
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error

# Encode categoricals
for col in ["State_Name", "Season", "Crop"]:
    le = LabelEncoder()
    df[col + "_enc"] = le.fit_transform(df[col])
    encoders[col] = le

features = ["State_Name_enc", "Season_enc", "Crop_enc", "Area"]
X, y = df[features], df["yield_t_ha"]

model = GradientBoostingRegressor(
    n_estimators=200,
    learning_rate=0.1,
    max_depth=5,
    subsample=0.8,
    random_state=42
)
```

#### Scenario: Expected metrics
- R² score on test set: ≥ 0.90
- Mean Absolute Error: ≤ 0.5 t/ha

---

### Requirement: Fertilizer Recommendation Dataset

The system SHALL use the Kaggle fertilizer prediction dataset for the fertilizer model.

#### Scenario: Dataset access
- **Name**: Fertilizer Prediction Dataset
- **Source**: https://www.kaggle.com/datasets/gdabhishek/fertilizer-prediction
- **File**: `Fertilizer Prediction.csv`
- **Rows**: 99 (small — handle with stratified CV, no test split)
- **Features**: Temperature, Humidity, Moisture, Soil Type, Crop Type, Nitrogen, Potassium, Phosphorous
- **Target**: `Fertilizer Name` (7 classes)

#### Scenario: Training note
- GIVEN only 99 rows exist
- WHEN training
- THEN use 5-fold stratified cross-validation as the primary evaluation metric
- AND do NOT do a train/test split (too small; CV is more reliable)

#### Scenario: Training script key parameters
```python
model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
# expected CV: ~0.95
model.fit(X, y)  # refit on all data for production
```

---

### Requirement: PlantVillage Dataset (Disease Detection)

The system SHALL use the PlantVillage dataset for ResNet34 fine-tuning.

#### Scenario: Dataset access
- **Name**: PlantVillage Dataset
- **Source (Kaggle)**: https://www.kaggle.com/datasets/emmarex/plantdisease
- **Source (GitHub)**: https://github.com/spMohanty/PlantVillage-Dataset
- **Images**: 54,305
- **Classes**: 38 (14 plant species, healthy + diseased variants)
- **Format**: JPEG, organized in class-named folders
- **Size**: ~827 MB unzipped

#### Scenario: Download procedure
```bash
kaggle datasets download -d emmarex/plantdisease -p data/plant_disease/
unzip data/plant_disease/plantdisease.zip -d data/plant_disease/raw/
# folder structure: data/plant_disease/raw/PlantVillage/<class_name>/*.JPG
```

---

### Requirement: Background Removal Pre-Processing for Training Data

The system SHALL pre-process the PlantVillage training images by removing backgrounds before
training ResNet34. Research confirms this improves in-field generalisation accuracy.

#### Scenario: Pre-process dataset before training

- GIVEN the raw PlantVillage images at `data/plant_disease/raw/PlantVillage/`
- WHEN the preprocessing script `scripts/preprocess_bg_remove.py` is run
- THEN `rembg.remove()` is applied to every image in every class folder
- AND the background-removed images (white background, same class-folder structure) are
  saved to `data/plant_disease/processed/PlantVillage/`
- AND the training script reads from `data/plant_disease/processed/` (not `raw/`)

#### Scenario: Pre-processing script

```python
from pathlib import Path
from PIL import Image
import rembg

src = Path("data/plant_disease/raw/PlantVillage")
dst = Path("data/plant_disease/processed/PlantVillage")

for cls_dir in src.iterdir():
    out_dir = dst / cls_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    for img_path in cls_dir.glob("*.JPG"):
        if (out_dir / img_path.name).exists():
            continue
        with open(img_path, "rb") as f:
            result = rembg.remove(f.read())
        img = Image.open(io.BytesIO(result)).convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=Image.open(io.BytesIO(result)).split()[3])
        bg.save(out_dir / img_path.name, "JPEG", quality=95)
```

#### Scenario: rembg dependency

- `rembg==2.0.57` and `onnxruntime` are added to `requirements-train.txt`
- The U2Net model is downloaded automatically on first run (~170 MB, cached by rembg)

---

### Requirement: ResNet34 Training

The system SHALL fine-tune a pretrained ResNet34 on PlantVillage using PyTorch.

#### Scenario: Training script key parameters
```python
import torch
import torchvision.models as models
import torchvision.transforms as T
from torch.utils.data import DataLoader, random_split
from torchvision.datasets import ImageFolder

# Transforms
train_tf = T.Compose([
    T.RandomResizedCrop(128),
    T.RandomHorizontalFlip(),
    T.ColorJitter(brightness=0.2, contrast=0.2),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])
val_tf = T.Compose([
    T.Resize(144),
    T.CenterCrop(128),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

dataset = ImageFolder("data/plant_disease/raw/PlantVillage", transform=train_tf)
n_val = int(0.2 * len(dataset))
train_ds, val_ds = random_split(dataset, [len(dataset) - n_val, n_val])
val_ds.dataset.transform = val_tf

train_loader = DataLoader(train_ds, batch_size=64, shuffle=True,  num_workers=4)
val_loader   = DataLoader(val_ds,   batch_size=64, shuffle=False, num_workers=4)

# Model
model = models.resnet34(weights="IMAGENET1K_V1")
model.fc = torch.nn.Linear(model.fc.in_features, 38)

# Training config
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)
criterion = torch.nn.CrossEntropyLoss()
epochs = 25
```

#### Scenario: Expected metrics
- Validation accuracy: ≥ 0.94
- Top-3 accuracy: ≥ 0.99
- Epochs to convergence: 15–25 (depends on GPU)
- Training time estimate: ~45 min on RTX 3060 / ~3 hrs on CPU

#### Scenario: Model saving
```python
torch.save({
    "model_state_dict": model.state_dict(),
    "class_to_idx": dataset.class_to_idx,
    "idx_to_class": {v: k for k, v in dataset.class_to_idx.items()},
    "val_accuracy": best_val_acc,
    "epoch": best_epoch
}, "apps/ml-vision/models/resnet34_plantvillage.pth")
```

---

### Requirement: Model Versioning

All saved model files SHALL include metadata for reproducibility.

#### Scenario: Crop model artifact
- `apps/ml-crop/models/crop_model.pkl` — contains `{model, scaler, features, trained_at, val_accuracy}`

#### Scenario: Yield model artifact
- `apps/ml-crop/models/yield_model.pkl` — contains `{model, encoders, features, trained_at, r2_score}`

#### Scenario: Fertilizer model artifact
- `apps/ml-crop/models/fertilizer_model.pkl` — contains `{model, label_encoders, features, trained_at, cv_accuracy}`

#### Scenario: Vision model artifact
- `apps/ml-vision/models/resnet34_plantvillage.pth` — PyTorch checkpoint with class mapping, validation accuracy, and epoch

#### Scenario: Training environment
- All Python training scripts run under `uv` with a locked `requirements-train.txt`
- CUDA is used if available; training falls back to CPU without code changes
- `torch.manual_seed(42)` and `numpy.random.seed(42)` are set at the top of every training script
