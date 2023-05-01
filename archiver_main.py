from hashlib import sha256
import json
from datetime import datetime
from tqdm import tqdm
from types import SimpleNamespace

import downloader
import storage


def findLatestModel(modelVersions):
    latestModel = modelVersions[0]
    # adapt for Z time 
    latestDate = datetime.fromisoformat(latestModel.createdAt.replace('Z', ''))
    for modelVersion in modelVersions:
        creationDate = datetime.fromisoformat(modelVersion.createdAt.replace('Z', ''))
        version = modelVersion.name
        if creationDate > latestDate:
            latestModel = modelVersion
            latestDate = creationDate

    return latestModel

def findFiles(files):
    filteredFiles = []

    # compensate for undefined tensor size
    safeTensor = []
    safeTensorPruned = []
    safeTensorFull = []
    # compensate for undefined tensor size
    pickleTensor =[]
    pickleTensorPruned = []
    pickleTensorFull = []

    # preferably reach a full Safetensor
    for file in files:
        if hasattr(file.metadata, "format"):
            if file.metadata.format == "SafeTensor":
                if hasattr(file.metadata, "size"):
                    if file.metadata.size == "full":
                        safeTensorFull.append(file)
                    else:
                        safeTensorPruned.append(file)
                # if size not provided add anyway
                else:
                    safeTensor.append(file)

            elif file.metadata.format == "PickleTensor":
                if hasattr(file.metadata, "size"):
                    if file.metadata.size == "full":
                        pickleTensorFull.append(file)
                    else:
                        pickleTensorPruned.append(file)
                # if size not provided add anyway
                else:
                    pickleTensor.append(file)
            elif file.metadata.format == "Other":
                filteredFiles.append(file)

        #if no format provided add anyway
        else:
            filteredFiles.append(file)

    if len(safeTensorFull) > 0:
        safeTensor.extend(safeTensorFull)
    else:
        safeTensor.extend(safeTensorPruned)

    # SafeTensors found
    if len(safeTensor) > 0:
        filteredFiles.extend(safeTensor)
        return filteredFiles
    
    # fallback to PickleTensors
    if len(pickleTensorFull) > 0:
        pickleTensor.extend(pickleTensorFull)
    else:
        pickleTensor.extend(pickleTensorPruned)

    filteredFiles.extend(pickleTensor)

    return filteredFiles



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
    config.onlyCalculateSizes = configData["only_size"]                                #@param {type:"boolean"}
    # Force Recheck intended for when you want to recheck all models
    # Or to move favorites into the favorites folder
    config.forceRecheck = configData["force_recheck"]                                  #@param {type:"boolean"}
    config.getSmallFilesAnyway = configData["get_small_files"]  
    config.favoritesOnly = configData["favorites_only"]                                #@param {type:"boolean"}
    #@title Select Types to Scrape
    config.includeCheckpoints = configData["include_checkpoints"]                      #@param {type:"boolean"}
    config.includeLora = configData["include_lora"]                                    #@param {type:"boolean"}
    config.includeTextualInversionEmbeds = configData["include_textual_inversion"]     #@param {type:"boolean"}
    config.includeHypernets = configData["include_hypernets"]                          #@param {type:"boolean"}
    config.includeAestheticGrads = configData["include_aesthetic_grads"]               #@param {type:"boolean"}
    config.includeControlNet = configData["include_control_net"]                       #@param {type:"boolean"}
    config.includePoses = configData["include_poses"]                                  #@param {type:"boolean"}


    return config

def printConfiguration(config):
    border = "=" * 50
    print(f"\n{border}\n       Running Civitai Archiver v{config.version}\n{border}\n")
    print(f"       Settings\n{border}\n")
    print(f"API: {config.apiKey}")
    print(f"Include Types:")
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

    sessionDownloadedFileCount = 0
    sessionBownloadedBytes = 0
    failedHashes = 0

    config = loadConfiguration()
    archivedModels = storage.loadMemory(config)
    if config.debugMode:
        printConfiguration(config)    

    allModels = downloader.getModels(config)


#    if(config.onlyCalculateSizes):    

    size = 0
    for model in tqdm(allModels, desc="Stats from models", leave=True, position=0, smoothing=0):
        if len(model.modelVersions)> 0:
            # only take latest model
            modelVersion = findLatestModel(model.modelVersions)

            # for Checkpoints filter out "redundant" files to lower space usage
            if model.type == "Checkpoint":
                # try to find Safetensor file with PickleTensor as fallback
                # also include Other Types
                modelFiles = findFiles(modelVersion.files)
            else:
                modelFiles = modelVersion.files

            for file in modelFiles:
                size += file.sizeKB
                #print(f"File: {file.name}, Type: {file.metadata.format}, Size: {file.sizeKB}")

                #for modelFile in model.modelVersions[0].files:
                #    if hasattr(modelFile, "primary"):
                #        if modelFile.primary:
                #            size += modelFile.sizeKB

            archivedModels.items.append(model)
            storage.saveMemory(archivedModels, config)
        else:
            print(f"Model has NO Versions: {model.id}")

    #sizeGB =  size / 1000000
    #sizeTB = sizeGB / 1000

    print(f"Found models:[count: {len(allModels)}, size: {size}KB ]")


if __name__ == '__main__':
    main()