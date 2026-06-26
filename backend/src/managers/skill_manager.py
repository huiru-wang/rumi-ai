from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SkillMeta:
    name: str
    description: str
    file_path: str


class SkillManager:
    """Scans a skills directory for SKILL.md files, provides list and load capabilities.

    Agent is unaware of any skill business logic — it only sees name + description.
    Follows the LangChain Skills pattern (progressive disclosure).
    """

    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, SkillMeta] = {}
        self._scan()

    def _scan(self):
        if not self.skills_dir.exists():
            return
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            meta = self._parse_frontmatter(skill_file)
            if meta:
                self._skills[meta.name] = meta

    def _parse_frontmatter(self, path: Path) -> SkillMeta | None:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None
        end_index = content.index("---", 3)
        front = yaml.safe_load(content[3:end_index])
        return SkillMeta(
            name=front["name"],
            description=front.get("description", ""),
            file_path=str(path),
        )

    def list_skills(self) -> list[dict]:
        return [
            {"name": skill.name, "description": skill.description}
            for skill in self._skills.values()
        ]

    def load_skill(self, name: str) -> str | None:
        skill = self._skills.get(name)
        if not skill:
            return None
        return Path(skill.file_path).read_text(encoding="utf-8")

    def load_reference(self, skill_name: str, reference_path: str) -> str | None:
        """Backward-compatible wrapper around load_file()."""
        return self.load_file(skill_name, reference_path)

    def load_file(self, skill_name: str, relative_path: str) -> str | None:
        """Load a file relative to the skill directory.

        Example: load_file("ppt", "references/themes.md")
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return None
        skill_dir = Path(skill.file_path).parent
        file_path = (skill_dir / relative_path).resolve()
        # Prevent escaping the skill directory.
        if skill_dir.resolve() not in file_path.parents and file_path != skill_dir.resolve():
            return None
        if not file_path.exists() or not file_path.is_file():
            return None
        return file_path.read_text(encoding="utf-8")

    def list_references(self, skill_name: str) -> list[str]:
        """List available reference files for a skill."""
        skill = self._skills.get(skill_name)
        if not skill:
            return []
        ref_dir = Path(skill.file_path).parent / "references"
        if not ref_dir.exists():
            return []
        return sorted(f.name for f in ref_dir.iterdir() if f.is_file() and f.suffix == ".md")

    def list_linked_files(self, skill_name: str) -> dict[str, list[str]]:
        """返回技能的所有关联文件，按类型分组"""
        linked: dict[str, list[str]] = {}
        skill = self._skills.get(skill_name)
        if not skill:
            return linked
        base = Path(skill.file_path).parent
        for subdir in ["references", "templates", "scripts", "assets"]:
            dir_path = base / subdir
            if dir_path.exists():
                linked[subdir] = sorted(
                    str(file_path.relative_to(dir_path)).replace("\\", "/")
                    for file_path in dir_path.rglob("*")
                    if file_path.is_file()
                )
        return linked

    def load_files(self, skill_name: str, file_paths: list[str]) -> dict[str, str | None]:
        """批量加载文件，返回 {path: content} 字典"""
        results: dict[str, str | None] = {}
        for path in file_paths:
            results[path] = self.load_file(skill_name, path)
        return results
