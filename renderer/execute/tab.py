from dataclasses import dataclass
from itertools import cycle
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, FrozenSet
from cjworkbench.sync import database_sync_to_async
from cjwkernel.types import RenderResult, Tab
from cjwstate.rendercache import load_cached_render_result, CorruptCacheError
from cjwstate.models import WfModule, Workflow
from cjwstate.models.param_spec import ParamDType
from .wf_module import execute_wfmodule, locked_wf_module
from .types import UnneededExecution


logger = logging.getLogger(__name__)


class cached_property:
    """
    Memoizes a property by replacing the function with the retval.
    """

    def __init__(self, func):
        self.__doc__ = getattr(func, "__doc__")
        self._func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self

        func = self._func
        value = func(obj)
        obj.__dict__[func.__name__] = value
        return value


@dataclass(frozen=True)
class ExecuteStep:
    wf_module: WfModule
    schema: ParamDType.Dict
    params: Dict[str, Any]


@dataclass(frozen=True)
class TabFlow:
    """
    Sequence of steps in a single Tab.

    This is a data class: there are no database queries here. In particular,
    querying for `.stale_steps` gives the steps that were stale _at the time of
    construction_.
    """

    tab: Tab
    steps: List[ExecuteStep]

    @property
    def tab_slug(self) -> str:
        return self.tab.slug

    @cached_property
    def first_stale_index(self) -> int:
        """
        Index into `self.steps` of the first WfModule that needs rendering.

        `None` if the entire flow is fresh.
        """
        cached_results = [step.wf_module.cached_render_result for step in self.steps]
        try:
            # Stale WfModule means its .cached_render_result is None.
            return cached_results.index(None)
        except ValueError:
            return None

    @cached_property
    def stale_steps(self) -> List[ExecuteStep]:
        """
        Just the steps of `self.steps` that need rendering.

        `[]` if the entire flow is fresh.
        """
        index = self.first_stale_index
        if index is None:
            return []
        else:
            return self.steps[index:]

    @cached_property
    def last_fresh_wf_module(self) -> Optional[WfModule]:
        """
        The first fresh step.
        """
        stale_index = self.first_stale_index
        if stale_index is None:
            stale_index = len(self.steps)
        fresh_index = stale_index - 1
        if fresh_index < 0:
            return None
        return self.steps[fresh_index].wf_module

    @cached_property
    def input_tab_slugs(self) -> FrozenSet[str]:
        """
        Slugs of tabs that are used as _input_ into this tab's steps.
        """
        ret = set()
        for step in self.steps:
            schema = step.schema
            slugs = set(schema.find_leaf_values_with_dtype(ParamDType.Tab, step.params))
            ret.update(slugs)
        return frozenset(ret)


@database_sync_to_async
def _load_input_from_cache(
    workflow: Workflow, flow: TabFlow, path: Path
) -> RenderResult:
    last_fresh_wfm = flow.last_fresh_wf_module
    if last_fresh_wfm is None:
        return RenderResult()
    else:
        # raises UnneededExecution
        with locked_wf_module(workflow, last_fresh_wfm) as safe_wfm:
            crr = safe_wfm.cached_render_result
            assert crr is not None  # otherwise it's not fresh, see?

            try:
                # Read the entire input Parquet file.
                return load_cached_render_result(crr, path)
            except CorruptCacheError:
                raise UnneededExecution


async def execute_tab_flow(
    workflow: Workflow,
    flow: TabFlow,
    tab_results: Dict[Tab, Optional[RenderResult]],
    output_path: Path,
) -> RenderResult:
    """
    Ensure `flow.tab.live_wf_modules` all cache fresh render results.

    `tab_results.keys()` must be ordered as the Workflow's tabs are.

    Raise `UnneededExecution` if something changes underneath us such that we
    can't guarantee all render results will be fresh. (The remaining execution
    is "unneeded" because we assume another render has been queued.)

    WEBSOCKET NOTES: each wf_module is executed in turn. After each execution,
    we notify clients of its new columns and status.
    """
    logger.debug(
        "Rendering Tab(%d, %s - %s)", workflow.id, flow.tab_slug, flow.tab.name
    )

    # Execute one module at a time.
    #
    # We don't hold any lock throughout the loop: the loop can take a long
    # time; it might be run multiple times simultaneously (even on
    # different computers); and `await` doesn't work with locks.
    #
    # We pass data between two Arrow files, kinda like double-buffering. The
    # two are `output_path` and `buffer_path`. This requires fewer temporary
    # files, so it's less of a hassle to clean up.
    fd, buffer_filename = tempfile.mkstemp(prefix="render-buffer.arrow")
    os.close(fd)
    buffer_path = Path(buffer_filename)

    # Choose the right input file, such that the final render is to
    # `output_path`. For instance:
    #
    # [cache] -> A -> B -> C: A and C use `output_path`.
    # [cache] -> A -> B: cache and B use `output_path`.
    #
    # The first retval of `next(step_output_paths)` will be used by the cache.
    if len(flow.stale_steps) % 2 == 1:
        # [cache], A, B, C => cache gets buffer_path
        step_output_paths = cycle([buffer_path, output_path])
    else:
        # [cache], A, B => cache gets output_path
        step_output_paths = cycle([output_path, buffer_path])

    try:
        last_result = await _load_input_from_cache(
            workflow, flow, next(step_output_paths)
        )
        for step, step_output_path in zip(flow.stale_steps, step_output_paths):
            step_output_path.write_bytes(b"")  # don't leak data from two steps ago
            next_result = await execute_wfmodule(
                workflow,
                step.wf_module,
                step.params,
                flow.tab,
                last_result,
                tab_results,
                step_output_path,
            )
            last_result = next_result
        return last_result
    finally:
        buffer_path.unlink()
