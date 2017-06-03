import pymongo

def connect_mongodb():
    mongo_ip = "localhost"
    mongo_port = 27017
    #user_name = "root"
    #password = "nlpnju"

#    mongo_uri = "mongodb://" + user_name + ":" + password + '@'+ mongo_ip + ':' + str(mongo_port)
    mongo_uri = "mongodb://localhost:27017"
    mongo_connection = pymongo.Connection(mongo_uri)

    return mongo_connection

