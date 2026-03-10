from pymilvus import (
    Collection,
    CollectionSchema,
    MilvusClient,
    Partition,
    connections,
    utility,
)


class MilvusHandler:
    def __init__(self, host, port, init=False):
        self.host = host
        self.port = port
        self.connection = None
        self.connect()
        # app을 구동하면 collection을 release 시킨다.
        if init:
            self.collections_release()

    def connect(self):
        self.connection = connections.connect(host=self.host, port=self.port)

    def disconnect(self):
        if self.connection is not None:
            connections.disconnect()

    def collections_release(self):
        url = f"http://root:Milvus@{self.host}:{self.port}"
        client = MilvusClient(url)
        list_collection = client.list_collections()
        for collection in list_collection:
            if collection != "chatsam":
                self.collection_release(collection)

    def get_replicas(self, target):
        # target : collection , partition
        result = target.get_replicas()
        return result

    # collection의 state : loaded , not loaded
    def load_state(self, collection_name):
        return utility.load_state(collection_name)

    def get_collection(self, collection_name):
        return Collection(collection_name)

    def get_partition(self, collection, partition_name):
        return collection.partition(partition_name=partition_name)

    def collection_load_by_name(self, collection_name):
        collection = Collection(collection_name)
        self.collection_load(collection)

    def collection_load(self, collection, partition_name=None, replica_number=None):
        if partition_name and replica_number:
            collection.load(partition_name=partition_name, replica_number=replica_number)
        elif partition_name:
            collection.load(partition_name=partition_name)
        elif replica_number:
            collection.load(replica_number=replica_number)
        else:
            collection.load()

    def partition_load(self, partition, partition_name, replica_number=None):
        if replica_number:
            partition.load(replica_number=replica_number)
        else:
            partition.load()

    def collection_release(self, collection_name):
        has = utility.has_collection(collection_name)
        if has:
            collection = Collection(collection_name)
            collection.release()

    def partition_release(self, partition_name):
        partition = Partition(partition_name)
        partition.release()

    def collection_flush(self, collection):
        collection.flush()

    def get_collection_count(self, collection):
        return collection.num_entities

    def create_collection(self, collection_name, fields, dimension):
        schema = CollectionSchema(
            fields=fields,
            description=f"{collection_name} collection",
            enable_dynamic_field=True,
        )
        # schema.enable_dynamic_field(True)
        return Collection(collection_name, schema, consistency_level="Strong")

    def create_partition(self, collection, partition_name, description=None):
        partition = collection.create_partition(partition_name=partition_name, description=description)
        # print(f"create partition : {partition}")
        return partition

    def create_index(self, collection, col, index_params=None):
        collection.create_index(field_name=col, index_params=index_params)

    def drop_collection(self, collection_name):
        utility.drop_collection(collection_name)

    def drop_partition(self, collection, partition_name):
        collection.drop_partition(partition_name)

    def insert_data(self, collection, data, partition_name=None):
        if partition_name:
            ins_result = collection.insert(data, partition_name)
        else:
            ins_result = collection.insert(data)
        return ins_result

    def delete_data(self, collection, expr):
        res = collection.delete(expr)
        return res

    def search(
        self,
        collection,
        data,
        field,
        search_params,
        output_fields,
        partition_names=None,
        expr=None,
        top_k=1,
        limit=10,
        batch_size=2,
    ):
        if partition_names:
            return collection.search(
                data=data,
                anns_field=field,
                param=search_params,
                limit=limit,
                batch_size=batch_size,
                partition_names=partition_names,
                expr=expr,
                output_fields=output_fields,
                top_k=top_k,
            )
        else:
            return collection.search(
                data=data,
                anns_field=field,
                param=search_params,
                limit=limit,
                expr=expr,
                batch_size=batch_size,
                output_fields=output_fields,
                top_k=top_k,
            )

    def query(
        self,
        collection,
        expr,
        output_fields,
        partition_names=None,
        offset=0,
        top_k=16384,
    ):
        if partition_names:
            return collection.query(
                expr=expr,
                output_fields=output_fields,
                partition_names=partition_names,
                limit=top_k,
                offset=offset,
            )
        else:
            return collection.query(expr=expr, output_fields=output_fields, limit=top_k, offset=offset)

    def list_partition(self, collection):
        result = []
        partitions = collection.partitions
        for partition in partitions:
            print(f"{self.get_partition(collection, partition.name)}")
            result.append({"id": partition.name, "doc": partition.description})

        return result
