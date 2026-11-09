import logging
from collections.abc import Iterator

from graphql import FieldNode, OperationDefinitionNode
from strawberry.extensions import SchemaExtension

logger = logging.getLogger("booking_api.graphql")


class OperationLogger(SchemaExtension):
    def on_execute(self) -> Iterator[None]:
        ctx = self.execution_context
        operation = self._find_operation(ctx.graphql_document, ctx.operation_name)
        if operation is not None:
            name = operation.name.value if operation.name else "anonymous"
            for selection in operation.selection_set.selections:
                if isinstance(selection, FieldNode):
                    logger.info("RECV graphql %s %s", name, selection.name.value)
        yield

    @staticmethod
    def _find_operation(document, operation_name: str | None) -> OperationDefinitionNode | None:
        if document is None:
            return None
        operations = [d for d in document.definitions if isinstance(d, OperationDefinitionNode)]
        if operation_name is None:
            return operations[0] if len(operations) == 1 else None
        return next((op for op in operations if op.name and op.name.value == operation_name), None)
