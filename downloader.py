import json
import time
from datetime import datetime
import os
import requests
from tqdm import tqdm
from types import SimpleNamespace

import storage


headers = {
    'User-Agent': 'Civitai Model Archiver - API Client'    
}

def getTypeFilters(config):
    typesToDownload = []
    # Parse Types into an array
    # All available types Checkpoint, TextualInversion, Hypernetwork, AestheticGradient, LORA, Controlnet, Poses
    if config.includeCheckpoints:
        typesToDownload.append('Checkpoint')
    if config.includeLora:
        typesToDownload.append('LORA')
    if config.includeTextualInversionEmbeds:
        typesToDownload.append('TextualInversion')
    if config.includeHypernets:
        typesToDownload.append('Hypernetwork')
    if config.includeAestheticGrads:
        typesToDownload.append('AestheticGradient')
    if config.includeControlNet:
        typesToDownload.append('Controlnet')
    if config.includePoses:
        typesToDownload.append('Poses')

    if len(typesToDownload) == 7: # If all types are selected, don't filter
        typesToDownload = []

    print(f"Downloading Types: {typesToDownload}")
    return typesToDownload


def getRequestWithRetry(url, headers, params =[], retries = 4):

    for retryN in range(retries):
        r = requests.get(url, params=params, headers=headers)
        if r.status_code == 200:
            return r
        print(f"Failed to get {url} with status code {r.status_code}, [{retryN}] retrying in 5 seconds...")
        print(params)
        time.sleep(5)
    print(f"Giving up on {url} with status code {r.status_code}")
    print(params)
    return None


def getModels(config):
    print("Requesting Models")    
    # "query": "Nothing"
    # "username": "Kavka"
    params = {
        "limit": 100,
        "page": 1,
        "sort":"Newest"  
    }

    typesToDownload = getTypeFilters(config)

    try:
        if config.favoritesOnly:
            params["favorites"] = "true"
            headers["Authorization"] = f"Bearer {config.apiKey}"
        if typesToDownload != [] and typesToDownload != None:
            params["types"] = typesToDownload
    except:
        print("No types specified, getting everything...")

    models = []

    print(f"Requesting Models with params: {params}")
    modelsRequest = getRequestWithRetry("https://civitai.com/api/v1/models",  headers=headers, params=params)

    # coudn't get Model information
    if modelsRequest == None:
        print(f"Unable to request Models: params: {params}")
        return models
    # Parse JSON into an object with attributes corresponding to dict keys.
    responseJSON = json.loads(modelsRequest.text, object_hook=lambda d: SimpleNamespace(**d))
    models.extend(responseJSON.items)

    if config.debugMode:
        print(f"Model Stats:[metadata: {responseJSON.metadata}]")

    if config.onlyFirstPage:
        return models

    # only one page returned
    if not hasattr(responseJSON.metadata, "nextPage"):
        return models

    pbar = tqdm( desc="Downloading model page(s)",total=responseJSON.metadata.totalPages)
    pbar.update(1)
    while hasattr(responseJSON.metadata, "nextPage"):
        modelsRequest = getRequestWithRetry(responseJSON.metadata.nextPage,  headers=headers)
        if modelsRequest != None:
            responseJSON = json.loads(modelsRequest.text, object_hook=lambda d: SimpleNamespace(**d))
            models.extend(responseJSON.items)
        else:
            del(responseJSON.nextPage)
        pbar.update(1)


    return models    

def downloadFileChunked(response, filename, totalSizeBytes, speedThreshold=5):
    blockSize = 1024 * 1024 * 20  # 20 MB chunk size
    progressBar = tqdm(total=totalSizeBytes, unit='iB', unit_scale=True, desc=f"{filename}", leave=False)

    startTime = progressBar._time()

    with open(filename, 'wb') as file:
        for data in response.iter_content(blockSize):
            progressBar.update(len(data))
            file.write(data)

            endTime = progressBar._time()
            timeElapsed = endTime - startTime
            totalDataDownloaded = progressBar.n

            if timeElapsed > 0:
                downloadSpeedMb = (totalDataDownloaded / timeElapsed) / (1024 * 1024)  # speed in Mb/s

                if downloadSpeedMb < speedThreshold and totalSizeBytes > 1024 * 1024 * 100: # If the file is less than 100MB, don't worry about the speed
                    progressBar.close()
                    return False, progressBar.n
    progressBar.close()
    return True, progressBar.n

def downloadFile(config, url, modelType, hash, filename, modelName, filesize, retries=4):
    sessionDownloadedBytes = 0

    filename = os.path.join(modelName, filename)
    filename = os.path.join(modelType, filename)

    for retryN in range(retries):
        #if storage.checkFile(config, filename, hash):
        #    return sessionDownloadedBytes, True
        response = requests.get(url, stream=True, headers=headers)
        if response.status_code == 429:
            print(f"Rate limited, waiting 30 seconds {retryN}...")
            time.sleep(30)
            continue

        totalSizeBytes = int(response.headers.get('content-length', 0))
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        isDownloadSuccessful, downloadSize = downloadFileChunked(response, filename, totalSizeBytes)

        if not isDownloadSuccessful or (totalSizeBytes != 0 and totalSizeBytes != downloadSize):
            print(f"ERROR, something went wrong with {filename}, retrying {retryN}...")
            continue

        sessionDownloadedBytes += totalSizeBytes
        return sessionDownloadedBytes, False

    return sessionDownloadedBytes, True

def findLatestModelVersion(modelVersions):
    latestModel = modelVersions[0]
    # adapt for Z time 
    latestDate = datetime.fromisoformat(latestModel.createdAt.replace('Z', ''))
    for modelVersion in modelVersions:
        creationDate = datetime.fromisoformat(modelVersion.createdAt.replace('Z', ''))
        if creationDate > latestDate:
            latestModel = modelVersion
            latestDate = creationDate

    return latestModel

def filterFilesOtherType(files):
    filteredFiles = []

    for file in files:
        # if no format provided, for Other type, add to final list
        if not hasattr(file.metadata, "format") or file.metadata.format == "Other": 
            filteredFiles.append(file)
            
    return filteredFiles

def filterFilesByType(files, fileType):
    filteredFiles = []
    tensorPruned = []
    tensorFull = []
    # preferably reach a full Tensor
    for file in files:
        # if no format provided, for Other type, add to final list
        if not hasattr(file.metadata, "format"):
            if fileType == "Other":
                filteredFiles.append(file)
            continue

        if file.metadata.format == fileType:
            # if no size provided add to safetensor list 
            if not hasattr(file.metadata, "size"):
                filteredFiles.append(file)
                continue

            if file.metadata.size == "full":
                tensorFull.append(file)
                continue
            
            tensorPruned.append(file)

    if len(tensorFull) > 0:
        filteredFiles.extend(tensorFull)
        return filteredFiles
    
    filteredFiles.extend(tensorPruned)
    return filteredFiles

def findFiles(files):
    filteredFiles = []

    otherFiles = filterFilesOtherType(files)
    filteredFiles.extend(otherFiles)

    safeTensor = filterFilesByType(files, "SafeTensor")

    # SafeTensors found
    if len(safeTensor) > 0:
        filteredFiles.extend(safeTensor)
        return filteredFiles
    
    # fallback to PickleTensor
    pickleTensor = filterFilesByType(files, "PickleTensor")
    filteredFiles.extend(pickleTensor)
    return filteredFiles

def downloadModelVersion(config,modelVersion,modelType,modelName):
    size = 0
    # for Checkpoints filter out "redundant" files to lower space usage
    if modelType == "Checkpoint":
        # try to find Safetensor file with PickleTensor as fallback
        # also include Other Types
        modelFiles = findFiles(modelVersion.files)
    # rest are acceptable size, possible optimization in later version
    else:
        modelFiles = modelVersion.files

    for file in modelFiles:
        if(config.onlyCalculateSizes):
            size += file.sizeKB
            continue
                #print(f"File: {file.name}, Type: {file.metadata.format}, Size: {file.sizeKB}")
        fileHash = None
        if hasattr(file.hashes, "SHA256"):
            fileHash = file.hashes.SHA256
        downloadFile(config, file.downloadUrl, file.type, fileHash, file.name, modelName, file.sizeKB)
        size += file.sizeKB
    
    return size, len(modelFiles)
