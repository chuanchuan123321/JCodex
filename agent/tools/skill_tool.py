"""Skill loading tool - allows AI to load skill content on demand"""


class SkillTool:
    """Tool for loading skill content"""

    def __init__(self, skills_loader):
        """
        Initialize SkillTool

        Args:
            skills_loader: SkillsLoader instance
        """
        self.skills_loader = skills_loader

    def load_skill(self, skill_name: str) -> tuple[bool, str]:
        """
        Load a skill's complete content with file structure

        Args:
            skill_name: Name of the skill to load

        Returns:
            Tuple of (success, result)
        """
        try:
            # Check if skill exists
            available_skills = self.skills_loader.list_skills(filter_unavailable=False)
            skill_names = [s["name"] for s in available_skills]

            if skill_name not in skill_names:
                return (
                    False,
                    f"❌ Skill '{skill_name}' not found. Available skills: {', '.join(skill_names)}",
                )

            # Check if skill is available (dependencies met)
            skill = next((s for s in available_skills if s["name"] == skill_name), None)
            if not self.skills_loader._check_skill_available(skill):
                missing = self.skills_loader._get_missing_requirements(skill)
                return (
                    False,
                    f"❌ Skill '{skill_name}' is unavailable. Missing: {', '.join(missing)}",
                )

            # Load skill content
            content = self.skills_loader.load_skill(skill_name)
            if not content:
                return False, f"❌ Failed to load skill '{skill_name}'"

            # Get skill directory and list files
            skill_dir = self.skills_loader._find_skill_dir(skill_name)
            file_structure = self._get_file_structure(skill_dir)

            return (
                True,
                f"""✅ Loaded skill: {skill_name}

## 📁 Skill 目录结构

{file_structure}

## 📖 Skill 内容

{content}""",
            )

        except Exception as e:
            return False, f"❌ Error loading skill: {str(e)}"

    def _get_file_structure(self, skill_dir) -> str:
        """
        Get the file structure of a skill directory

        Args:
            skill_dir: Path to skill directory

        Returns:
            Formatted file structure string
        """
        try:
            from pathlib import Path

            if not skill_dir or not skill_dir.exists():
                return "无法获取文件结构"

            # Get parent directory (workspace/skills)
            parent_dir = skill_dir.parent
            parent_name = parent_dir.name  # "skills"
            grandparent_name = parent_dir.parent.name  # "workspace"

            lines = []
            lines.append(f"```")
            lines.append(f"{grandparent_name}/{parent_name}/{skill_dir.name}/")

            # List all items in the skill directory
            items = sorted(skill_dir.iterdir())
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                prefix = "└── " if is_last else "├── "

                if item.is_dir():
                    lines.append(f"{prefix}{item.name}/")
                    # List items in subdirectory
                    try:
                        subitems = sorted(item.iterdir())
                        for j, subitem in enumerate(subitems):
                            is_last_sub = j == len(subitems) - 1
                            subprefix = "    └── " if is_last_sub else "    ├── "
                            lines.append(f"{subprefix}{subitem.name}")
                    except:
                        pass
                else:
                    lines.append(f"{prefix}{item.name}")

            lines.append(f"```")
            return "\n".join(lines)
        except Exception as e:
            return f"无法获取文件结构: {str(e)}"

    def list_available_skills(self) -> tuple[bool, str]:
        """
        List all available skills

        Returns:
            Tuple of (success, result)
        """
        try:
            skills = self.skills_loader.list_skills(filter_unavailable=True)

            if not skills:
                return True, "No skills available"

            result = "Available skills:\n\n"
            for skill in skills:
                result += f"- **{skill['name']}**: {skill.get('description', 'N/A')}\n"

            return True, result

        except Exception as e:
            return False, f"❌ Error listing skills: {str(e)}"
