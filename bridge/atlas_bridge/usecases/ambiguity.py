"""When a request does not say enough to choose among the routes that fit it."""

from ..core.http import PathTemplate


class Underdetermined:
    """A request whose unknown parameter sits where the routes that fit it have different fixed words
    ('/projects/{p}/{kind}/{id}' against '.../inboxes/{pk}' and '.../states/{pk}') names none of them: which one it
    reaches depends on a value the code does not show. Routes that only differ in parameter names, or that declare the
    same fixed path twice, do not make it underdetermined."""

    @staticmethod
    def of(sent: PathTemplate, served: list[PathTemplate]) -> bool:
        if len(served) < 2:
            return False
        for i, segment in enumerate(sent.segments):
            if segment.is_literal:
                continue
            words = {r.segments[i].text for r in served if i < len(r.segments) and r.segments[i].is_literal}
            if len(words) > 1:
                return True
        return False
