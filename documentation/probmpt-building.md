entry point cli/app.py comes from core/settings.py prompt_sections: tuple[str, ...] = ("soul", "user", "tool")

now when the harness builder from app.py calls core/harness.py -> _build_agent() prompt = self.prompt_builder.build(
    spec, tools, dynamic = {environment}
    project root.
)
in the core/prompt.py
now the dynamic sections get environment data.