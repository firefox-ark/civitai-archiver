import json
import os
from hashlib import sha256
from types import SimpleNamespace

class NsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, SimpleNamespace):
            return obj.__dict__
        return super(NsEncoder, self).default(obj)

memoryFile = "memory.json"

def loadMemory(config):
    if config.onlyCalculateSizes:
        memory = SimpleNamespace()
        memory.items = []
        return memory
    if not os.path.exists(memoryFile):
        with open(memoryFile, "w") as f:
            memory = SimpleNamespace()
            memory.items = []
            json.dump(memory.__dict__, f, indent=4)
            f.close()
        return memory
    
    with open("memory.json", "r") as f:
        memory = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
        f.close()
    return memory

def saveMemory(memory, config):
    if config.onlyCalculateSizes:
        return
    
    global memoryObjectIsLocked
    memoryObjectIsLocked = True

    if config.debugMode:
        print("Writing to memory")

    with open(memoryFile, "w") as f:
        json.dump(memory,f, cls=NsEncoder, indent=4)
        f.close()

    memoryObjectIsLocked = False

def updateMemory(archivedModels, config, model):
    for i, modelStored in enumerate(archivedModels.items):
        if model.id == modelStored.id:
            archivedModels.items[i] = model
            break

    saveMemory(archivedModels, config)

def findModelInMemory(config,modelId):
    currentModels = loadMemory(config)
    for model in currentModels:
        if model.id == modelId:
            return model
    return None

def isModelInMemory(model, archivedModels):
    for modelStored in archivedModels.items:
        if model.id == modelStored.id:
            if model.latestVersionId == modelStored.latestVersionId:
                return True, True
            return True, False
        
    return False, False


def moveFileToFolder(src, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    dest = os.path.join(dest_folder, os.path.basename(src))
    os.rename(src, dest)
    return dest

def checkSha256Checksum(filename, hash):
    if hash is None:
        raise "No hash found"

    print("Reading Hash...")
    with open(filename, "rb") as f:
        sha256_hash = sha256()
        readFILE = f.read()
        sha256_hash.update(readFILE)
    print("Done reading hash!")

    if sha256_hash.hexdigest() != hash.lower():
        print(f"{filename} Hash doesn't match expected and actual hashes:")
        print(sha256_hash.hexdigest())
        print(hash)
        return False
    return True

def checkFile(config,filename, hash):
    check = checkSha256Checksum(filename, hash)
    if config.debugMode:
        print(f"{filename} sha256 hash matches, skipping...")
    return check
