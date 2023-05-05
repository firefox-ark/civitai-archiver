from hashlib import sha256
import json
from tqdm import tqdm
from types import SimpleNamespace

import downloader
import storage


def loadConfiguration():
    # Read configuration from the file
    with open("config.json", "r") as conf:
        configData = json.load(conf)
        conf.close() 

    config = SimpleNamespace()

    config.version = "1.0.0"
    config.apiKey = configData["civitai_api_key"]
    config.debugMode = configData["debug_mode"]

    # Doesn't download anything
    config.onlyCalculateSizes = configData["only_size"]                                 #@param {type:"boolean"}
    config.onlyFirstPage = configData["only_first_page"]                                 #@param {type:"boolean"}
    # Force Recheck intended for when you want to recheck all models
    # Or to move favorites into the favorites folder
    config.forceRecheck = configData["force_recheck"]                                   #@param {type:"boolean"}
    config.getSmallFilesAnyway = configData["get_small_files"]  
    config.favoritesOnly = configData["favorites_only"]                                 #@param {type:"boolean"}
    config.maxThreads = configData["maximum_threads"]                                    #@param {type:"str"}
    #@title Select Types to Scrape
    config.includeCheckpoints = configData["include_checkpoints"]                       #@param {type:"boolean"}
    config.includeLora = configData["include_lora"]                                     #@param {type:"boolean"}
    config.includeTextualInversionEmbeds = configData["include_textual_inversion"]      #@param {type:"boolean"}
    config.includeHypernets = configData["include_hypernets"]                           #@param {type:"boolean"}
    config.includeAestheticGrads = configData["include_aesthetic_grads"]                #@param {type:"boolean"}
    config.includeControlNet = configData["include_control_net"]                        #@param {type:"boolean"}
    config.includePoses = configData["include_poses"]                                   #@param {type:"boolean"}


    return config

def printConfiguration(config):
    border = "=" * 50
    print(f"\n{border}\n       Running Civitai Archiver v{config.version}\n{border}\n")
    print(f"       Settings\n{border}\n")
    print(f"API: {config.apiKey}")
    print("Include Types:")
    print(f"    Checkpoints:                {config.includeCheckpoints}")
    print(f"    LORAs:                      {config.includeLora}")
    print(f"    Textual Inversion Embeds:   {config.includeTextualInversionEmbeds}")
    print(f"    Hypernets:                  {config.includeHypernets}")
    print(f"    Aesthetic Grads:            {config.includeAestheticGrads}")
    print(f"    ControlNet:                 {config.includeControlNet}")
    print(f"    Poses:                      {config.includePoses}")
    print(f"\n{border}\n")

def main():
    global memoryObjectIsLocked
    memoryObjectIsLocked = False

    specificallyRequestedModelIDs = ""
    sessionDownloadedFileCount = 0
    sessionBownloadedBytes = 0
    failedHashes = 0

    config = loadConfiguration()
    archivedModels = storage.loadMemory(config)
    if config.debugMode:
        printConfiguration(config)    

    allModels = downloader.getModels(config)
    print(f"Found models:[count: {len(allModels)}]")

    size = 0
    fileCount = 0
    modelsInMemory = 0
    for model in tqdm(allModels, desc="Archive models", leave=True, position=0, smoothing=0):
        if len(model.modelVersions)> 0:
            # only take latest model
            modelVersion = downloader.findLatestModelVersion(model.modelVersions)
            model.latestVersionId = modelVersion.id
        else:
            print(f"Model has NO Versions: {model.id}")
            continue
       
        # Check if the model has already been downloaded
        modelExists, isModelLatest = storage.isModelInMemory(model, archivedModels)
        
        if isModelLatest:
            modelsInMemory += 1
            continue
        
        # single thread model download
        # TODO: multi-threading in future version
        downloadSize, downloadFiles = downloader.downloadModelVersion(config, modelVersion, model.type, model.name)
        size += downloadSize
        fileCount += downloadFiles

        if modelExists:
            storage.updateMemory(archivedModels, config, model)
        else:
            archivedModels.items.append(model)
            storage.saveMemory(archivedModels, config)


    sizeGB = int(size / 1000000)

    border = "=" * 50
    print(f"\n{border}\n")
    print(f"Models already downloaded:  {modelsInMemory}")
    print(f"Total download files:   {fileCount}")
    print(f"Total download size:    {sizeGB}GB")
    print(f"\n{border}\n")

if __name__ == '__main__':
    main()