#!/usr/bin/env Rscript
# extract_metrics.R — Fit the 5 SARIMAX models from the original Rmd
# and extract AIC, BIC, log-likelihood for cross-validation with Python.
#
# Usage: Rscript extract_metrics.R
# Output: data/r_original/metricas_modelos_r.json

.libPaths(c("~/R/library", .libPaths()))
suppressPackageStartupMessages({
  library(readxl)
  library(forecast)
  library(jsonlite)
})

# --- Resolve paths ---
script_dir <- tryCatch(
  dirname(normalizePath(commandArgs(trailingOnly = FALSE)[
    grep("--file=", commandArgs(trailingOnly = FALSE))
  ] |> sub("--file=", "", x = _))),
  error = function(e) "."
)
# Project root: two levels up from data/r_original/
project_root <- normalizePath(file.path(script_dir, "..", ".."))

data_file <- file.path(project_root, "data", "Variaveis_para_Previsão_260105.xlsx")
if (!file.exists(data_file)) {
  data_file <- file.path(project_root, "data", "dados_sefaz.xlsx")
}
if (!file.exists(data_file)) {
  stop("No data file found. Expected Variaveis_para_Previsão_260105.xlsx or dados_sefaz.xlsx in data/")
}

cat("Reading data from:", data_file, "\n")

# --- Load data ---
data <- suppressMessages(as.data.frame(read_xlsx(data_file)))

# Parameters matching the Rmd (mes_atual = 10 for October 2025)
mes_atual <- 10

# --- Create time series ---
ICMS.ts    <- ts(data[, "icms_sp"],   start = c(2003, 1), end = c(2026, 12), freq = 12)
IBCBR.ts   <- ts(data[, "ibc_br"],   start = c(2003, 1), end = c(2026, 12), freq = 12)
IGPDI.ts   <- ts(data[, "igp_di"],   start = c(2003, 1), end = c(2026, 12), freq = 12)
DIASUTEIS.ts <- ts(data[, "dias_uteis"], start = c(2003, 1), end = c(2026, 12), freq = 12)

# --- Lags ---
IBCBR_lag <- stats::lag(IBCBR.ts, k = -1) |> window(end = c(2026, 12))
IGPDI_lag <- stats::lag(IGPDI.ts, k = -1) |> window(end = c(2026, 12))

# --- Dummies ---
LS2008NOV <- ts(0, start = c(2003, 1), end = c(2026, 12), freq = 12)
window(LS2008NOV, start = c(2008, 11), end = c(2026, 12)) <- 1

TC2020APR04 <- ts(0, start = c(2003, 1), end = c(2026, 12), freq = 12)
window(TC2020APR04, start = c(2020, 4), end = c(2020, 7)) <- 1

TC2022OUT05 <- ts(0, start = c(2003, 1), end = c(2026, 12), freq = 12)
window(TC2022OUT05, start = c(2022, 10), end = c(2023, 5)) <- 1

dummies_icms1 <- ts.union(LS2008NOV, TC2020APR04, TC2022OUT05)

# --- Training window ---
training_date2 <- c(2025, mes_atual)

# --- Fit models ---
results <- list()

cat("\n--- Modelo 1: auto.arima SARIMA + dias_uteis + dummies ---\n")
# The Rmd uses auto.arima which selected (1,1,1)(0,0,0,12).
# We fit with the fixed order for reproducibility.
tryCatch({
  m1 <- Arima(window(ICMS.ts, end = training_date2),
              order = c(1, 1, 1), seasonal = c(0, 0, 0),
              xreg = window(ts.union(DIASUTEIS.ts, dummies_icms1),
                            end = training_date2),
              lambda = 0)
  cat("  AIC:", m1$aic, " BIC:", m1$bic, " loglik:", m1$loglik, "\n")
  results[["Modelo 1"]] <- list(
    aic      = round(m1$aic, 4),
    bic      = round(m1$bic, 4),
    loglik   = round(m1$loglik, 4),
    order    = c(1, 1, 1),
    seasonal = c(0, 0, 0, 12),
    exog     = c("dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"),
    n_obs    = m1$nobs,
    sigma2   = round(m1$sigma2, 8)
  )
}, error = function(e) {
  cat("  ERROR:", conditionMessage(e), "\n")
  results[["Modelo 1"]] <<- list(error = conditionMessage(e))
})

cat("\n--- Modelo 2: SARIMAX(3,1,0)(2,0,0,12) + IGP-DI lag1, IBC-BR lag1, dias_uteis + dummies ---\n")
tryCatch({
  m2 <- Arima(window(ICMS.ts, end = training_date2),
              order = c(3, 1, 0), seasonal = c(2, 0, 0),
              xreg = window(ts.union(IGPDI_lag, DIASUTEIS.ts, IBCBR_lag,
                                     dummies_icms1),
                            end = training_date2),
              method = "ML", include.mean = TRUE, lambda = 0)
  cat("  AIC:", m2$aic, " BIC:", m2$bic, " loglik:", m2$loglik, "\n")
  results[["Modelo 2"]] <- list(
    aic      = round(m2$aic, 4),
    bic      = round(m2$bic, 4),
    loglik   = round(m2$loglik, 4),
    order    = c(3, 1, 0),
    seasonal = c(2, 0, 0, 12),
    exog     = c("igp_di_lag1", "dias_uteis", "ibc_br_lag1", "LS2008NOV", "TC2020APR04", "TC2022OUT05"),
    n_obs    = m2$nobs,
    sigma2   = round(m2$sigma2, 8)
  )
}, error = function(e) {
  cat("  ERROR:", conditionMessage(e), "\n")
  results[["Modelo 2"]] <<- list(error = conditionMessage(e))
})

cat("\n--- Modelo 3: SARIMAX(0,1,1)(0,1,1,12) + IGP-DI, IBC-BR, IBC-BR lag1, dias_uteis + dummies ---\n")
tryCatch({
  m3 <- Arima(window(ICMS.ts, end = training_date2),
              order = c(0, 1, 1), seasonal = c(0, 1, 1),
              xreg = window(ts.union(IGPDI.ts, IBCBR_lag, IBCBR.ts,
                                     DIASUTEIS.ts, dummies_icms1),
                            end = training_date2),
              method = "ML", include.mean = TRUE, lambda = 0)
  cat("  AIC:", m3$aic, " BIC:", m3$bic, " loglik:", m3$loglik, "\n")
  results[["Modelo 3"]] <- list(
    aic      = round(m3$aic, 4),
    bic      = round(m3$bic, 4),
    loglik   = round(m3$loglik, 4),
    order    = c(0, 1, 1),
    seasonal = c(0, 1, 1, 12),
    exog     = c("igp_di", "ibc_br_lag1", "ibc_br", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"),
    n_obs    = m3$nobs,
    sigma2   = round(m3$sigma2, 8)
  )
}, error = function(e) {
  cat("  ERROR:", conditionMessage(e), "\n")
  results[["Modelo 3"]] <<- list(error = conditionMessage(e))
})

cat("\n--- Modelo 4: SARIMAX(0,1,1)(0,1,2,12) + IBC-BR, IBC-BR lag1, dias_uteis + dummies ---\n")
tryCatch({
  m4 <- Arima(window(ICMS.ts, end = training_date2),
              order = c(0, 1, 1), seasonal = c(0, 1, 2),
              xreg = window(ts.union(IBCBR_lag, IBCBR.ts,
                                     DIASUTEIS.ts, dummies_icms1),
                            end = training_date2),
              method = "ML", include.mean = TRUE, lambda = 0)
  cat("  AIC:", m4$aic, " BIC:", m4$bic, " loglik:", m4$loglik, "\n")
  results[["Modelo 4"]] <- list(
    aic      = round(m4$aic, 4),
    bic      = round(m4$bic, 4),
    loglik   = round(m4$loglik, 4),
    order    = c(0, 1, 1),
    seasonal = c(0, 1, 2, 12),
    exog     = c("ibc_br_lag1", "ibc_br", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"),
    n_obs    = m4$nobs,
    sigma2   = round(m4$sigma2, 8)
  )
}, error = function(e) {
  cat("  ERROR:", conditionMessage(e), "\n")
  results[["Modelo 4"]] <<- list(error = conditionMessage(e))
})

cat("\n--- Modelo 5: SARIMAX(0,1,1)(0,1,2,12) + IGP-DI, IBC-BR, IBC-BR lag1 + dummies ---\n")
tryCatch({
  m5 <- Arima(window(ICMS.ts, end = training_date2),
              order = c(0, 1, 1), seasonal = c(0, 1, 2),
              xreg = window(ts.union(IGPDI.ts, IBCBR_lag, IBCBR.ts,
                                     dummies_icms1),
                            end = training_date2),
              method = "ML", include.mean = TRUE, lambda = 0)
  cat("  AIC:", m5$aic, " BIC:", m5$bic, " loglik:", m5$loglik, "\n")
  results[["Modelo 5"]] <- list(
    aic      = round(m5$aic, 4),
    bic      = round(m5$bic, 4),
    loglik   = round(m5$loglik, 4),
    order    = c(0, 1, 1),
    seasonal = c(0, 1, 2, 12),
    exog     = c("igp_di", "ibc_br_lag1", "ibc_br", "LS2008NOV", "TC2020APR04", "TC2022OUT05"),
    n_obs    = m5$nobs,
    sigma2   = round(m5$sigma2, 8)
  )
}, error = function(e) {
  cat("  ERROR:", conditionMessage(e), "\n")
  results[["Modelo 5"]] <<- list(error = conditionMessage(e))
})

# --- Write output ---
output_file <- file.path(project_root, "data", "r_original", "metricas_modelos_r.json")
json_out <- toJSON(results, auto_unbox = TRUE, pretty = TRUE)
writeLines(json_out, output_file)
cat("\nMetrics saved to:", output_file, "\n")

# --- Summary ---
cat("\n=== Summary ===\n")
for (nm in names(results)) {
  r <- results[[nm]]
  if (!is.null(r$error)) {
    cat(sprintf("  %-10s  ERROR: %s\n", nm, r$error))
  } else {
    cat(sprintf("  %-10s  AIC=%10.4f  BIC=%10.4f  loglik=%10.4f  n_obs=%d\n",
                nm, r$aic, r$bic, r$loglik, r$n_obs))
  }
}
