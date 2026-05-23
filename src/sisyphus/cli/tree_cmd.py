from pathlib import Path
from sisyphus.pipeline.sleep import SleepPipeline


def cmd_tree_rebuild(base_path, use_llm=False):
    pp = SleepPipeline(base_path)
    return pp.run(steps=["tree", "moc", "link"], use_llm=use_llm)


def cmd_tree_full_sleep(base_path, use_llm=False, force=False):
    pp = SleepPipeline(base_path)
    return pp.run(use_llm=use_llm, force=force)
