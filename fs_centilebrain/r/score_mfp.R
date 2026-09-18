#!/usr/bin/env Rscript
# Score rows of (age, ICV[, region volumes]) with a CentileBrain MFP model list.
#
#   Rscript score_mfp.R --model MFPmodels_subcorticalvolume_male.rds --offsets offsets.csv \
#                       --sex male --input rows.csv --output scored.csv
#
# Input CSV: one row per case with columns `age`, `ICV` and optionally any of the region
# columns (Lthal, ...). Region names, order and model indices come from the offsets file.
#
# Output CSV (long format): one row per (input row, region):
#   row, region, predicted, rmse, z, percentile_empirical
# `predicted` includes the centering offset K, i.e. it equals the website's prediction.
# `z` and `percentile_empirical` are NA when the region volume is not in the input.
# percentile_empirical is the mid-rank of the case's residual among the model's training
# residuals, in percent.
#
# This mirrors the upstream script (CentileBrainWebsite/src/Model/model2.html.js):
#   predicted <- predict(mfp_model, newdata = data.frame(age, ICV))
#   z <- (observed - predicted) / sqrt(sum(residuals^2) / length(residuals))
# except that prediction is done on the inner glm (`$fit`) so the `mfp` package is not needed,
# and the (unpublished) centering means are replaced by the equivalent offsets K.

args <- commandArgs(trailingOnly = TRUE)
opt <- list()
i <- 1
while (i <= length(args)) {
  key <- sub("^--", "", args[i]); opt[[key]] <- args[i + 1]; i <- i + 2
}
for (k in c("model", "offsets", "sex", "input", "output")) {
  if (is.null(opt[[k]])) stop("missing --", k)
}

offsets <- read.csv(opt[["offsets"]], stringsAsFactors = FALSE)
offsets <- offsets[offsets$sex == opt[["sex"]], ]
if (nrow(offsets) == 0) stop("no offsets for sex ", opt[["sex"]])
if (basename(opt[["model"]]) != unique(offsets$model_file)) {
  stop("offsets were derived for ", unique(offsets$model_file), " but model is ", basename(opt[["model"]]))
}

models <- readRDS(opt[["model"]])
if (length(models) != nrow(offsets)) stop("model list has ", length(models), " entries, offsets has ", nrow(offsets))

rows <- read.csv(opt[["input"]], check.names = FALSE)
if (!all(c("age", "ICV") %in% names(rows))) stop("input must have columns age and ICV")
newdat <- data.frame(age = as.numeric(rows$age), ICV = as.numeric(rows$ICV))

out <- NULL
for (r in seq_len(nrow(offsets))) {
  region <- offsets$region[r]
  model <- models[[r]]
  fit <- model$fit
  attr(fit$terms, ".Environment") <- globalenv()
  predicted <- as.numeric(predict(fit, newdata = newdat)) + offsets$K[r]
  train_resid <- model$residuals
  rmse <- sqrt(mean(train_resid^2))
  stopifnot(abs(rmse - offsets$rmse[r]) < 1e-6)
  if (region %in% names(rows)) {
    observed <- as.numeric(rows[[region]])
    resid <- observed - predicted
    z <- resid / rmse
    pct <- vapply(resid, function(x) {
      if (is.na(x)) return(NA_real_)
      100 * (sum(train_resid < x) + 0.5 * sum(train_resid == x)) / length(train_resid)
    }, numeric(1))
  } else {
    z <- rep(NA_real_, nrow(rows)); pct <- z
  }
  out <- rbind(out, data.frame(row = seq_len(nrow(rows)) - 1L, region = region, predicted = predicted,
                               rmse = rmse, z = z, percentile_empirical = pct, stringsAsFactors = FALSE))
}
write.csv(out, opt[["output"]], row.names = FALSE)
