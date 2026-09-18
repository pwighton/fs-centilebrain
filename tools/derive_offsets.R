#!/usr/bin/env Rscript
# Derive the per-region centering offsets (K) that make local MFP predictions equal
# the centilebrain.org predictions, plus the training RMSE of each model.
#
#   K_region = website_prediction - predict(model$fit, age, ICV)
#
# The upstream models were fit on mean-centered data whose means are unpublished;
# see docs/model-notes.md section 2. Requires single-site website runs (no ComBat
# harmonization), for which the difference is an exact constant per region.
#
# Usage (inside the container, repo mounted at /repo):
#   Rscript tools/derive_offsets.R \
#       --model-dir /opt/centilebrain/models \
#       --input reference/web-results/input_single-site_demo.xlsx.csv \
#       --male   reference/web-results/single-site_male_2026-09-18-15-02-11 \
#       --female reference/web-results/single-site_female_2026-09-17-22-31-48 \
#       --output fs_centilebrain/data/offsets-subcortical.csv
#
# --input is the demo data as CSV (converted from the xlsx by tools/derive_offsets.sh).

args <- commandArgs(trailingOnly = TRUE)
opt <- list()
i <- 1
while (i <= length(args)) {
  key <- sub("^--", "", args[i]); opt[[key]] <- args[i + 1]; i <- i + 2
}
for (k in c("model-dir", "input", "male", "female", "output")) {
  if (is.null(opt[[k]])) stop("missing --", k)
}

regions <- c("Lthal","Rthal","Lcaud","Rcaud","Lput","Rput","Lpal","Rpal",
             "Lhippo","Rhippo","Lamyg","Ramyg","Laccumb","Raccumb")
demo <- read.csv(opt[["input"]], check.names = FALSE)
newdat <- data.frame(age = demo$age, ICV = demo$ICV)

out <- NULL
for (sex in c("male", "female")) {
  model_file <- sprintf("MFPmodels_subcorticalvolume_%s.rds", sex)
  models <- readRDS(file.path(opt[["model-dir"]], model_file))
  web_dir <- opt[[sex]]
  web <- read.csv(file.path(web_dir, sprintf("prediction_SubcorticalVolume_%s.csv", sex)), check.names = FALSE)
  stopifnot(nrow(web) == nrow(demo), all(web$SubjectID == demo$SubjectID))
  for (r in seq_along(regions)) {
    fit <- models[[r]]$fit
    attr(fit$terms, ".Environment") <- globalenv()
    local <- predict(fit, newdata = newdat)
    diff <- web[[regions[r]]] - local
    K <- mean(diff)
    spread <- max(abs(diff - K))
    if (spread > 1e-6) {
      stop(sprintf("%s %s: website - local is not constant (max deviation %.3g); was this a single-site run?",
                   sex, regions[r], spread))
    }
    resid <- models[[r]]$residuals
    out <- rbind(out, data.frame(
      measure = "subcortical", sex = sex, region = regions[r],
      K = K, rmse = sqrt(mean(resid^2)), n_train = length(resid),
      max_abs_dev = spread, source = basename(web_dir), model_file = model_file,
      stringsAsFactors = FALSE))
  }
  cat(sprintf("%s: %d regions, max |website - local - K| = %.3g mm3\n", sex, length(regions), max(out$max_abs_dev[out$sex == sex])))
}
write.csv(out, opt[["output"]], row.names = FALSE)
cat("wrote", opt[["output"]], "\n")
