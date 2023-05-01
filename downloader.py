import json
import time
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
#    session = requests.Session()

    for retryN in range(retries):
        r = requests.get(url, params=params, headers=headers)
        if r.status_code == 200:
            return r
        print(f"Failed to get {url} with status code {r.status_code}, retrying in 5 seconds...")
        print(params)
        time.sleep(5)
    print(f"Giving up on {url} with status code {r.status_code}")
    print(params)
    return None


def getModels(config):
    print(f"Requesting Models")    
    # "query": "Nothing"
    # "username": "Kavka"
    # "query": "test2",
    params = {
        "limit": 100,
        "page": 1,
        "query": "test2",
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
    modelsRequest = getRequestWithRetry(f"https://civitai.com/api/v1/models",  headers=headers, params=params)

    # coudn't get Model information
    if modelsRequest == None:
        print(f"Unable to request Models: params: {params}")
        return models
    # Parse JSON into an object with attributes corresponding to dict keys.
    responseJSON = json.loads(modelsRequest.text, object_hook=lambda d: SimpleNamespace(**d))
    models.extend(responseJSON.items)

    if config.debugMode:
        print(f"Model Stats:[metadata: {responseJSON.metadata}]")

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
        if storage.checkFile(config, filename, hash):
            return sessionDownloadedBytes, True
        response = requests.get(url, stream=True, headers=headers)
        if response.status_code == 429:
            print("Rate limited, waiting 30 seconds...")
            time.sleep(30)
            continue

        totalSizeBytes = int(response.headers.get('content-length', 0))
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        isDownloadSuccessful, downloadSize = downloadFileChunked(response, filename, totalSizeBytes)

        if not isDownloadSuccessful or (totalSizeBytes != 0 and totalSizeBytes != downloadSize):
            print(f"ERROR, something went wrong with {filename}, retrying...")
            continue

        sessionDownloadedBytes += totalSizeBytes
        return sessionDownloadedBytes, False

    return sessionDownloadedBytes, True