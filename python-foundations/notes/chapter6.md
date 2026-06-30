# Chapter 6

## Concepts Learned

- Lists
- List Items
- Indexes
- Negative Indexes
- Slices
- Mutable Data Types
- Immutable Data Types
- Tuples
- References
- Shallow Copy vs Deep Copy
- Sequence Data Types
- Multiple Assignment (Tuple Unpacking)
- List Enumeration
- Short-Circuit Evaluation
- Constants
- In-Place Modification

## Functions Learned

- `len()`
- `range()`
- `enumerate()`
- `list()`
- `tuple()`
- `type()`
- `input()`
- `print()`

## List Methods Learned

- `append()`
- `insert()`
- `remove()`
- `index()`
- `sort()`
- `reverse()`

## Modules Learned

- `random`
- `copy`
- `time`
- `sys`

## Random Module Functions

- `random.choice()`
- `random.shuffle()`
- `random.randint()`
- `random.random()`

## Copy Module Functions

- `copy.copy()`
- `copy.deepcopy()`

## Operators Learned

### List Operators

- `+` (Concatenation)
- `*` (Replication)

### Membership Operators

- `in`
- `not in`

### Augmented Assignment Operators

- `+=`
- `-=`
- `*=`
- `/=`
- `%=`

## List Operations

- Creating Lists
- Accessing Items by Index
- Using Negative Indexes
- Slicing Lists
- Updating Items
- Deleting Items
- Concatenating Lists
- Replicating Lists
- Sorting Lists
- Reversing Lists
- Searching Lists
- Adding Items
- Removing Items

## Sequence Features

Applicable to:

- Lists
- Strings
- Tuples
- Range Objects

Shared Operations:

- Indexing
- Slicing
- Iteration
- `len()`
- Membership Testing (`in`, `not in`)

## Common Errors

- `IndexError`
- `ValueError`
- `AttributeError`
- `TypeError`
- `NameError`

## Important Distinctions

### Lists

- Mutable
- Use square brackets `[]`
- Can be modified in place

### Tuples

- Immutable
- Use parentheses `()`
- Cannot be modified after creation

### Strings

- Immutable
- Sequence of characters

## Debugging Concepts Introduced

- Short-Circuit Evaluation
- Reference Sharing
- Mutable vs Immutable Objects
- Function Arguments Passed by Reference
- Side Effects from Shared Lists

## AI/ML Relevance

- Storing datasets as lists
- Managing batches of training data
- Feature collections
- Label storage
- Random sampling of data
- Shuffling datasets before training
- Tracking experiment metrics
- Understanding mutable objects during preprocessing
- Avoiding unintended data modifications through shared references
- Deep copying datasets and configurations before transformations

## Mini Projects Built

- Dynamic Cat Name Collector
- Pet Name Checker
- Magic 8 Ball (List Version)
- Coin Flip Streak Simulator
- Matrix Screensaver

## Key Takeaways

- Lists are ordered, mutable collections.
- Tuples are ordered, immutable collections.
- Variables store references, not actual values.
- Assigning one list variable to another copies the reference.
- Use `copy.copy()` for shallow copies.
- Use `copy.deepcopy()` for nested structures.
- Methods modify lists in place unless otherwise stated.
- `enumerate()` provides both index and value during iteration.
- `random.choice()` is often cleaner than using random indexes manually.
- Understanding references is critical for avoiding bugs in larger Python and AI/ML projects.