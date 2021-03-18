library(rsyncrosim)

function (ssimObject, data, name = NULL, fileData = NULL, append = NULL,
    forceElements = FALSE, force = FALSE, breakpoint = FALSE,
    import = TRUE, path = NULL)
{
    isFile <- NULL
    x <- ssimObject
    if (is.null(append)) {
        if (class(x) == "Scenario") {
            append <- FALSE
        }
        else {
            append <- TRUE
        }
    }
    args <- list()
    sheetNames <- .datasheets(x)
    if (is.null(path)) {
        e <- ssimEnvironment()
        if (!is.na(e$TransferDirectory)) {
            import <- FALSE
            path <- e$TransferDirectory
        }
    }
    if ((class(data) != "list") | (class(data[[1]]) != "data.frame")) {
        if (is.null(name)) {
            stop("Need a datasheet name.")
        }
        if (length(name) > 1) {
            stop("If a vector of names is provided, then data must be a list.")
        }
        if (!grepl("_", name, fixed = )) {
            name <- paste0("stsim_", name)
        }
        if (grepl("STSim_", name, fixed = TRUE)) {
            warning("An STSim_ prefix for a datasheet name is no longer required.")
            name <- paste0("stsim_", gsub("STSim_", "", name,
                fixed = TRUE))
        }
        hdat <- data
        data <- list()
        data[[name]] <- hdat
    }
    else {
        if (!is.null(name)) {
            if (length(name) != length(data)) {
                stop("Please provide a name for each element of data.")
            }
            warning("Name argument will override names(data).")
            names(data) <- name
        }
        else {
            name <- names(data)
        }
    }
    if (!is.null(fileData) && (length(data) > 1)) {
        stop("If fileData != NULL, data should be a dataframe, vector, or list of length 1.")
    }
    out <- list()
    for (i in seq(length.out = length(data))) {
        cName <- names(data)[i]
        cDat <- data[[cName]]
        if (class(cDat) != "data.frame") {
            cIn <- cDat
            if (length(cIn) == 0) {
                stop("No data found for ", cName)
            }
            if (!is.null(names(cDat))) {
                cDat <- data.frame(a = cIn[[1]])
                names(cDat) <- names(cIn)[1]
                for (j in seq(length.out = (length(cIn) - 1))) {
                  cDat[[names(cIn)[j + 1]]] <- cIn[[j + 1]]
                }
            }
            else {
                stop()
            }
        }
        for (kk in seq(length.out = ncol(cDat))) {
            if (class(cDat[[kk]]) == "factor") {
                cDat[[kk]] <- as.character(cDat[[kk]])
            }
        }
        scope <- sheetNames$scope[sheetNames$name == cName]
        if (length(scope) == 0) {
            sheetNames <- datasheets(x, refresh = TRUE)
            scope <- sheetNames$scope[sheetNames$name == cName]
            if (length(scope) == 0) {
                stop("Name not found in datasheetNames")
            }
        }
        if (is.null(fileData)) {
            tt <- command(c("list", "columns", "csv", "allprops",
                paste0("lib=", .filepath(x)), paste0("sheet=",
                  name)), .session(x))
            sheetInfo <- .dataframeFromSSim(tt)
            if (sum(grepl("isExternalFile^True", sheetInfo$properties,
                fixed = TRUE)) > 0) {
                sheetInfo$isFile <- grepl("isRaster^True", sheetInfo$properties,
                  fixed = TRUE)
            }
            else {
                sheetInfo$isFile <- grepl("isExternalFile^Yes",
                  sheetInfo$properties, fixed = TRUE)
            }
            sheetInfo <- subset(sheetInfo, isFile)
            sheetInfo <- subset(sheetInfo, is.element(name, names(cDat)))
        }
        if (!is.null(fileData)) {
            itemNames <- names(fileData)
            if (is.null(itemNames) || is.na(itemNames) || (length(itemNames) ==
                0)) {
                stop("names(fileData) must be defined, and each element must correspond uniquely to an entry in data")
            }
            sheetInfo <- subset(datasheet(x, summary = TRUE,
                optional = TRUE), name == cName)
            fileDir <- .filepath(x)
            if (sheetInfo$isOutput) {
                fileDir <- paste0(fileDir, ".output")
            }
            else {
                fileDir <- paste0(fileDir, ".input")
            }
            fileDir <- paste0(fileDir, "/Scenario-", .scenarioId(x),
                "/", cName)
            dir.create(fileDir, showWarnings = FALSE, recursive = TRUE)
            for (j in seq(length.out = length(itemNames))) {
                cFName <- itemNames[j]
                cItem <- fileData[[cFName]]
                if (!class(cItem) == "RasterLayer") {
                  stop("rsyncrosim currently only supports Raster layers as elements of fileData.")
                }
                findName <- cDat == cFName
                findName[is.na(findName)] <- FALSE
                sumFind <- sum(findName == TRUE, na.rm = TRUE)
                if (sumFind > 1) {
                  stop("Each element of names(fileData) must correspond to at most one entry in data. ",
                    sumFind, " entries of ", cName, " were found in data.")
                }
                if (sumFind == 0) {
                  warning(cName, " not found in data. This element will be ignored.")
                  next
                }
                if (identical(basename(cFName), cFName)) {
                  cOutName <- paste0(fileDir, "/", cFName)
                }
                else {
                  cOutName <- cFName
                }
                if (!grepl(".tif", cOutName, fixed = TRUE)) {
                  cDat[findName] <- paste0(cDat[findName], ".tif")
                  cOutName <- paste0(cOutName, ".tif")
                }
                raster::writeRaster(cItem, cOutName, format = "GTiff",
                  overwrite = TRUE)
            }
        }
        for (j in seq(length.out = ncol(cDat))) {
            if (is.factor(cDat[[j]])) {
                cDat[[j]] <- as.character(cDat[[j]])
            }
            if (is.logical(cDat[[j]])) {
                inCol <- cDat[[j]]
                cDat[[j]][inCol] <- "Yes"
                cDat[[j]][!inCol] <- "No"
            }
        }
        cDat[is.na(cDat)] <- ""
        pathBit <- NULL
        if (is.null(path)) {
            if (breakpoint) {
                pathBit <- paste0(.filepath(x), ".temp/Data")
            }
            else {
                pathBit <- .tempfilepath(x)
            }
        }
        else {
            pathBit <- path
        }
        dir.create(pathBit, showWarnings = FALSE, recursive = TRUE)
        if (append) {
            tempFile <- paste0(pathBit, "/", "SSIM_APPEND-",
                cName, ".csv")
        }
        else {
            tempFile <- paste0(pathBit, "/", "SSIM_OVERWRITE-",
                cName, ".csv")
        }
        write.csv(cDat, file = tempFile, row.names = FALSE, quote = TRUE)
        if (breakpoint) {
            out[[cName]] <- "Saved"
            next
        }
        if (import) {
            args <- list(import = NULL, lib = .filepath(x), sheet = cName,
                file = tempFile)
            tt <- "saved"
            if (nrow(cDat) > 0) {
                if (scope == "project") {
                  args[["pid"]] <- .projectId(x)
                  args <- c(args, list(append = NULL))
                }
                if (scope == "scenario") {
                  args[["sid"]] <- .scenarioId(x)
                  if (append)
                    args <- c(args, list(append = NULL))
                }
                tt <- command(args, .session(x))
            }
            if (tt[[1]] == "saved") {
                unlink(tempFile)
            }
            out[[cName]] <- tt
        }
        else {
            out[[cName]] <- "Saved"
        }
        if (out[[cName]] == "saved") {
            message(paste0("Datasheet <", cName, "> saved"))
            out[[cName]] <- TRUE
        }
        else {
            message(out[[cName]])
            out[[cName]] <- FALSE
        }
    }
    if (!forceElements && (length(out) == 1)) {
        out <- out[[1]]
    }
    unlink(.tempfilepath(x), recursive = TRUE)
    return(invisible(out))
}
<bytecode: 0x7ffff6959cc8>
<environment: namespace:rsyncrosim>

Signatures:
        ssimObject
target  "SsimObject"
defined "SsimObject"
