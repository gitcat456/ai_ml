epochs = [
    {"epoch": 1, "loss": 0.45, "accuracy": 0.81},
    {"epoch": 2, "loss": 0.31, "accuracy": 0.87},
    {"epoch": 3, "loss": 0.22, "accuracy": 0.91}
]

with open("training.log", "w") as file:
    for epoch in epochs:
        file.write(f"Epoch: {epoch['epoch']}\n")
        file.write(f"Loss: {epoch['loss']}\n")
        file.write(f"Accuracy: {epoch['accuracy']}\n")
        file.write("-" * 20 + "\n")

with open("training.log") as file:
    print(file.read())
          
   














