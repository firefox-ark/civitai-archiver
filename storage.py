import json
import os
from hashlib import sha256
from types import SimpleNamespace

class nsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, SimpleNamespace):
            return obj.__dict__
        return super(nsEncoder, self).default(obj)

def loadMemory(config):
    if config.onlyCalculateSizes:
        memory = SimpleNamespace()
        memory.items = []
        return memory
    if not os.path.exists("memory.json"):
        with open("memory.json", "w") as f:
            memory = SimpleNamespace()
            memory.items = []
            json.dump(memory.__dict__, f)
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

    #with open("memory.json", "w") as f:
    #    json.dump(memory.__dict__, f)
    #    f.close()
    #print(memory)

    memory_instance = SimpleNamespace(memory=memory)

    with open("memory.json", "w") as f:
        json.dump(memory_instance.__dict__, f)
        f.close()


    memoryObjectIsLocked = False

def findModelInMemory(config,modelId):
    currentModels = loadMemory(config)
    for model in currentModels:
        if model.id == modelId:
            return model
    return None

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
