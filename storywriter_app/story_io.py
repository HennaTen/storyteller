import json
import re
from pathlib import Path


def sanitize_filename(filename):
    return re.sub(r'(?u)[^-\w.]', '_', filename)


def _iter_layout_widgets(layout):
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is not None:
            yield widget


def story_widget_to_dict(story):
    story_data = {}
    story_data["title"] = story.title.text()
    story_data["summary"] = story.summary.toPlainText()
    story_data["summaryTokens"] = story.summary.tokenCount
    story_data["chapters"] = []
    for chapter in _iter_layout_widgets(story.chapterLayout):
        chapter_data = {}
        story_data["chapters"].append(chapter_data)
        chapter_data["title"] = chapter.title.text()
        chapter_data["summary"] = chapter.summary.toPlainText()
        chapter_data["summaryTokens"] = chapter.summary.tokenCount
        chapter_data["scenes"] = []
        for scene in _iter_layout_widgets(chapter.scenesLayout):
            scene_data = {}
            chapter_data["scenes"].append(scene_data)
            scene_data["summary"] = scene.summary.toPlainText()
            scene_data["summaryTokens"] = scene.summary.tokenCount
            scene_data["text"] = scene.text.toPlainText()
            scene_data["textTokens"] = scene.text.tokenCount
    return story_data


def story_widget_to_text(story):
    lines = []
    lines.append(story.title.text())
    lines.append("")
    for chapter in _iter_layout_widgets(story.chapterLayout):
        lines.append(chapter.title.text())
        lines.append("=" * len(chapter.title.text()))
        lines.append("")
        for scene in _iter_layout_widgets(chapter.scenesLayout):
            lines.append(scene.text.toPlainText())
            lines.append("")
    return "\n".join(lines)


def load_story_data(file_path):
    with open(file_path, "r", encoding="utf-8") as story_file:
        return json.load(story_file)


def save_story_data(file_path, story):
    Path(file_path).write_text(json.dumps(story_widget_to_dict(story)), encoding="utf-8")


def export_story_text(file_path, story):
    Path(file_path).write_text(story_widget_to_text(story), encoding="utf-8")
