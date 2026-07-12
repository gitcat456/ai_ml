from pathlib import Path

dataset = Path("datasets") / "train.csv"
print(dataset)

print(dataset.name)
print(dataset.suffix)
print(dataset.parent)

print(dataset.exists())

print(dataset.is_dir())
