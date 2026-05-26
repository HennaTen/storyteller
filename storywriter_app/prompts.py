def _layout_widgets(layout):
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is not None:
            yield widget


def _chapter_index(story, chapter):
    for index, widget in enumerate(_layout_widgets(story.chapterLayout)):
        if widget == chapter:
            return index
    return None


def _scene_index(chapter, scene):
    for index, widget in enumerate(_layout_widgets(chapter.scenesLayout)):
        if widget == scene:
            return index
    return None


def build_scene_prompt(scene):
    chapter = scene.parentChapter
    story = chapter.parentStory
    chapter_index = _chapter_index(story, chapter)
    scene_index = _scene_index(chapter, scene)

    prompt = '{{[INPUT]}}\nYou are to take the role of an author writing a story. The story is titled "' + story.title.text() + '".'
    if len(story.summary.toPlainText()) > 0:
        prompt = prompt + "\n\nGeneral background information: " + story.summary.toPlainText()
    prompt = prompt + "\n\nThe story so far has had the following major events happen:"
    for chapter_position in range(chapter_index + 1):
        current_chapter = story.chapterLayout.itemAt(chapter_position).widget()
        prompt = prompt + "\n\n" + current_chapter.summary.toPlainText()
    prompt = prompt + '\n\nThe current chapter is titled "' + chapter.title.text() + '"'
    if scene_index > 1:
        prompt = prompt + "\n\nThe following scenes have already happened in this chapter:"
        for scene_position in range(scene_index - 1):
            prompt = prompt + "\n" + chapter.scenesLayout.itemAt(scene_position).widget().summary.toPlainText()
    if scene_index > 0:
        prompt = prompt + "\n\nThe most recent scene before this one was:\n\n" + chapter.scenesLayout.itemAt(scene_index - 1).widget().text.toPlainText()

    prompt = prompt + "\n\nYou are now writing the next scene in which the following occurs: " + scene.summary.toPlainText() + "\n\nPlease write out this scene.\n{{[OUTPUT]}}"
    return prompt


def build_summary_prompt(chapter_widget):
    story = chapter_widget.parentStory
    chapter_index = _chapter_index(story, chapter_widget)
    if chapter_index == 0:
        return None

    chapter_index = chapter_index - 1
    prompt = '{{[INPUT]}}\nYou are to take the role of an author writing a story. The story is titled "' + story.title.text() + '".'
    if len(story.summary.toPlainText()) > 0:
        prompt = prompt + "\nGeneral background information: " + story.summary.toPlainText()
    prompt = prompt + "\n\nThe most recent chapter of the story is:"
    scenes_layout = story.chapterLayout.itemAt(chapter_index).widget().scenesLayout
    for scene in _layout_widgets(scenes_layout):
        prompt = prompt + "\n\n" + scene.text.toPlainText()

    prompt = prompt + "\n\nPlease summarize this chapter in 200 words or less, focusing on the information that's important for writing future scenes in this story.\n{{[OUTPUT]}}"
    return prompt
