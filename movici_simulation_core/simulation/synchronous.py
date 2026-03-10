from .common import SimulationRunner


class SynchronousSimulationRunner(SimulationRunner):
    """A SimulationRunner that connects all models and services in a single process, as opposed to
    the DistributedSimulationRunner that sets up models and services that run in a separate proces
    each and have them connect through TCP"""

    def run(self):
        pass


# class ModelRunner:
#     """
#     Provides logic for:
#
#     * Creating a Process (daemon=False) that runs a Model. Using a wrapping function, this
#         subprocess will:
#
#         * create the model with its model adapter
#         * create a (dealer) socket
#         * run the model
#         * catch exceptions from model, send ERROR message
#         * raise exceptions when not directly from model
#
#     * Fills the ModelInfo object
#
#     By creating the process as deamon=False, models can spawn their own subprocesses
#     """
#
#     update_handler: t.Optional[UpdateDataClient] = None
#     init_data_handler: t.Optional[ServicedInitDataHandler] = None
#     socket: t.Optional[MessageDealerSocket] = None
#
#     def __init__(
#         self,
#         model_info: ModelInfo,
#         settings: Settings,
#         strategies: list[type] | None = None,
#         schema: t.Optional[AttributeSchema] = None,
#     ):
#         self.settings = settings
#         self.model_info = model_info
#
#     def start(self):
#         proc = self.ctx.Process(
#             target=self.entry_point, daemon=False, name="Process-" + self.model_info.name
#         )
#         proc.start()
#         self.model_info.process = proc
#
#     def entry_point(self):
#         self.prepare_subprocess()
#         self.settings.name = self.model_info.name
#         logger = get_logger(self.settings)
#         self.socket = self._get_orchestrator_socket()
#         model = None
#
#         try:
#             set_timeline_info(self.settings.timeline_info)
#             stream = Stream(self.socket, logger=logger)
#             model = self._get_model(logger)
#
#             self._setup_model(stream, model)
#             stream.run()
#
#         except Exception as e:
#             self.socket.send(ErrorMessage(str(e)))
#             logger.critical(str(e))
#             logger.info(traceback.format_exc())
#             if model:
#                 # noinspection PyBroadException
#                 try:
#                     model.close(QuitMessage())
#                 except Exception:  # noqa: S110
#                     pass
#             sys.exit(1)
#         finally:
#             self.close()
#
#     def _get_model(self, logger):
#         model = self._ensure_model()
#         adapter = model.get_adapter()
#         wrapped = adapter(model=model, settings=self.settings, logger=logger)
#         wrapped.set_schema(self.schema)
#         return wrapped
#
#     def _ensure_model(self) -> Model:
#         if isinstance(self.model_info, ModelFromInstanceInfo):
#             return self.model_info.instance
#         elif isinstance(self.model_info, ModelFromTypeInfo):
#             return self.model_info.cls(self.model_info.config or {})
#         else:
#             raise ValueError("Unsupported ModelInfo")
#
#     def _setup_model(
#         self,
#         stream,
#         model: ModelAdapterBase,
#     ):
#         self.update_handler = UpdateDataClient(
#             self.settings.name, self.settings.service_discovery["update_data"]
#         )
#         self.init_data_handler = ServicedInitDataHandler(
#             self.settings.name, server=self.settings.service_discovery["init_data"]
#         )
#         serialization = strategies.get_instance(InternalSerializationStrategy)
#         connector = ModelConnector(
#             model, self.update_handler, self.init_data_handler, serialization=serialization
#         )
#         stream_handler = ConnectorStreamHandler(connector, stream)
#         stream_handler.initialize()
#
#     def _get_orchestrator_socket(self):
#         addr = self.settings.service_discovery["orchestrator"]
#         context = zmq.Context.instance()
#         socket: Socket = context.socket(zmq.DEALER)
#         socket.set(zmq.IDENTITY, self.settings.name.encode())
#         socket.connect(addr)
#         return MessageDealerSocket(socket)
#
#     def close(self):
#         self.socket.close(linger=1000)  # ms
#         if self.init_data_handler:
#             self.init_data_handler.close()
#         if self.update_handler:
#             self.update_handler.close()
#         if zmq.Context._instance is not None:
#             zmq.Context.instance().term()
