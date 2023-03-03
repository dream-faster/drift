# Why?

A single train/test split is an inadquate way to evaluate Time Series models.

# What?

With Continuous Validation, you take an existing time series, and:
- Train a model
- Evaluate the model on the next `n` steps
- Continue updating the model with the new data you just used for inference
- Evaluate the model on the next 1 to `n` steps.

This way, you can turn almost all of your data into an out of sample test set.

# Also knowns as

- Rolling Out-of-sample Evaluation
- Continuous Evaluation
- "Backtesting" (not to be confused with evaluation of static trading models)