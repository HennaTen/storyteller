from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFocusEvent
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .story_io import export_story_text, load_story_data, sanitize_filename, save_story_data
from .tasks import CountTask, GenerateTask, worker

exportedStylesheet = "background-color: rgb(252, 245, 229);"


def _layout_widgets(layout):
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is not None:
            yield widget


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)


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


def _build_scene_prompt(scene):
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


def _build_summary_prompt(chapter_widget):
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


class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super(CustomTextEdit, self).__init__(parent)
        self.parent = parent
        self.CustomTextEdit_oldText = self.toPlainText()

    def getText(self):
        return self.toPlainText()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        if self.CustomTextEdit_oldText != self.toPlainText():
            self.CustomTextEdit_oldText = self.toPlainText()
            self.parent.updateTokens()
        super().focusOutEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self.CustomTextEdit_oldText = self.toPlainText()
        super().focusInEvent(event)


class TokenizedTextEdit(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.tokenCountLabel = QLabel()
        self.tokenCount = 0
        self.textEdit = CustomTextEdit(self)
        self.layout.addWidget(self.textEdit)
        self.layout.addWidget(self.tokenCountLabel)

    def setText(self, text):
        if self.textEdit.getText() != text:
            self.textEdit.setText(text)
            self.updateTokens()

    def setPlainText(self, text):
        if self.textEdit.toPlainText() != text:
            self.textEdit.setPlainText(text)
            self.updateTokens()

    def setPlaceholderText(self, text):
        return self.textEdit.setPlaceholderText(text)

    def getText(self):
        return self.textEdit.getText()

    def toPlainText(self):
        return self.textEdit.toPlainText()

    def setPlainTextAndTokens(self, text, tokens):
        self.textEdit.setPlainText(text)
        if tokens < 0:
            self.updateTokens()
        else:
            self.onTokensCounted(tokens)

    def onTokensCounted(self, count):
        self.tokenCount = count
        self.tokenCountLabel.setText("Tokens: " + str(self.tokenCount))

    @pyqtSlot()
    def updateTokens(self):
        self.tokenCountLabel.setText("Counting tokens...")
        task = CountTask(self.textEdit.toPlainText(), self)
        worker.addTask(task)


class Scene(QWidget):
    sceneTextResponseReady = pyqtSignal(str)

    def __init__(self, parent_chapter, scene_data=None):
        super().__init__()
        self.parentChapter = parent_chapter
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.parentChapter.scenesLayout.addWidget(self)

        self.textLayout = QGridLayout()
        self.summary = TokenizedTextEdit()
        self.summary.setPlaceholderText("Scene Summary")
        self.summary.setMinimumHeight(100)
        self.textLayout.addWidget(QLabel("Scene Summary"), 0, 0)
        self.textLayout.addWidget(self.summary, 1, 0)

        self.summary.setToolTip(
            """This text is sent to the LLM to tell it what this scene is supposed to depict.
It is also used when generating later scenes in this chapter as part of the summary of how the chapter has progressed to this point."""
        )

        self.text = TokenizedTextEdit()
        self.text.setPlaceholderText("Text")
        self.text.setStyleSheet(exportedStylesheet)
        self.text.setToolTip("""This is the finished output text for this story.""")
        self.sceneTextResponseReady.connect(self.updateText)

        self.textLayout.addWidget(QLabel("Text"), 0, 1)
        self.textLayout.addWidget(self.text, 1, 1)

        self.layout.addLayout(self.textLayout)

        buttons = QHBoxLayout()

        self.move_up = QPushButton("Move up")
        self.move_up.clicked.connect(self.moveSceneUp)
        buttons.addWidget(self.move_up)
        self.move_down = QPushButton("Move down")
        self.move_down.clicked.connect(self.moveSceneDown)
        buttons.addWidget(self.move_down)

        self.generate_button = QPushButton("Generate text of this scene")
        self.generate_button.clicked.connect(self.generateScene)
        buttons.addWidget(self.generate_button)

        self.delete_button = QPushButton("Remove this scene")
        self.delete_button.clicked.connect(self.deleteScene)
        buttons.addWidget(self.delete_button)

        self.layout.addLayout(buttons)

        if scene_data:
            self.summary.setPlainTextAndTokens(scene_data["summary"], int(scene_data.get("summaryTokens", -1)))
            self.text.setPlainTextAndTokens(scene_data["text"], int(scene_data.get("textTokens", -1)))

    def deleteScene(self):
        self.parentChapter.scenesLayout.removeWidget(self)
        self.parentChapter.parentStory.update()
        self.deleteLater()

    def generateScene(self):
        prompt = _build_scene_prompt(self)
        print(prompt)
        task = GenerateTask(prompt, self)
        worker.addTask(task)
        self.text.setPlainTextAndTokens("Generating...", 0)

    def onResponseGenerated(self, response):
        self.sceneTextResponseReady.emit(response)

    def updateText(self, response):
        self.text.setPlainText(response)

    def moveScene(self, up):
        chapter = self.parentChapter
        scene_index = None
        scene_count = chapter.scenesLayout.count()
        for index in range(scene_count):
            if chapter.scenesLayout.itemAt(index).widget() == self:
                scene_index = index
                break
        target = scene_index
        if up:
            target = target - 1
        else:
            target = target + 1
        if target < 0 or target >= scene_count or scene_index < 0 or scene_index >= scene_count:
            return
        if scene_index > target:
            scene_index, target = target, scene_index
        layout = chapter.scenesLayout
        widget1 = layout.itemAt(scene_index).widget()
        widget2 = layout.itemAt(target).widget()
        layout.removeWidget(widget1)
        layout.removeWidget(widget2)
        layout.insertWidget(scene_index, widget2)
        layout.insertWidget(target, widget1)
        chapter.update()

    def moveSceneUp(self):
        self.moveScene(True)

    def moveSceneDown(self):
        self.moveScene(False)


class Chapter(QFrame):
    chapterSummaryTextResponseReady = pyqtSignal(str)

    def __init__(self, parent_story, chapter_data=None):
        super().__init__()
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(1)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.parentStory = parent_story

        title = QFormLayout()

        self.title = QLineEdit()
        self.title.setPlaceholderText("Chapter Title")
        self.title.setStyleSheet(exportedStylesheet)
        title.addRow("Chapter Title:", self.title)

        self.layout.addLayout(title)

        self.summary = TokenizedTextEdit()
        self.summary.setPlaceholderText("Previous Chapter Summary")
        self.summary.setMinimumHeight(100)
        self.summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        summary_label = QLabel("Summary of the\nprevious chapter:")
        generate_previous_button = QPushButton("Generate summary\nof previous chapter")
        generate_previous_button.clicked.connect(self.generateSummary)

        summary_container = QWidget()
        summary_container_layout = QGridLayout()
        summary_container.setLayout(summary_container_layout)
        summary_container_layout.addWidget(summary_label, 0, 0)
        summary_container_layout.addWidget(generate_previous_button, 1, 0)
        summary_container_layout.addWidget(self.summary, 0, 1, 2, 1)

        summary_container.setToolTip(
            """The summary of the previous chapter is used when prompting the LLM to provide it with context for how the story reached the current point.
Adding a summary of the "previous chapter" to the first chapter can be useful to provide background information that may not be relevant later in the story,
such as a description of how the characters got into the initial situation they first find themselves in.
You can use the AI to automatically generate a summary of the previous chapter's text, but it's good to review and edit it to ensure it focuses on what you consider important."""
        )
        self.chapterSummaryTextResponseReady.connect(self.updateSummaryText)

        self.layout.addWidget(summary_container)

        self.scenesWidget = QWidget()
        self.scenesLayout = QVBoxLayout()
        self.scenesLayout.setContentsMargins(20, 0, 0, 0)
        self.scenesWidget.setLayout(self.scenesLayout)

        self.layout.addWidget(self.scenesWidget)

        buttons = QHBoxLayout()

        self.add_scene_button = QPushButton("Add a new scene to this chapter")
        self.add_scene_button.clicked.connect(self.addScene)
        buttons.addWidget(self.add_scene_button)

        self.delete_button = QPushButton("Remove this chapter")
        self.delete_button.clicked.connect(self.deleteChapter)
        buttons.addWidget(self.delete_button)

        self.layout.addLayout(buttons)

        if chapter_data:
            self.title.setText(chapter_data["title"])
            self.summary.setPlainTextAndTokens(chapter_data["summary"], int(chapter_data.get("summaryTokens", -1)))
            for scene_data in chapter_data["scenes"]:
                Scene(self, scene_data)

        self.parentStory.chapterLayout.addWidget(self)
        self.parentStory.scrollContent.adjustSize()

    def deleteChapter(self):
        parent_layout = self.parentStory.chapterLayout
        parent_layout.removeWidget(self)
        self.deleteLater()
        self.parentStory.update()

    def addScene(self):
        Scene(self)

    def generateSummary(self):
        prompt = _build_summary_prompt(self)
        if prompt is None:
            return

        print("chapter index " + str(_chapter_index(self.parentStory, self) - 1))
        print(prompt)

        task = GenerateTask(prompt, self)
        worker.addTask(task)
        self.summary.setPlainTextAndTokens("Generating...", 0)

    def onResponseGenerated(self, response):
        self.chapterSummaryTextResponseReady.emit(response)

    def updateSummaryText(self, response):
        self.summary.setPlainText(response)


class StoryWriter(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Story writer")

        layout = QVBoxLayout()

        self.title = QLineEdit()
        self.title.setPlaceholderText("Title")
        self.title.setStyleSheet(exportedStylesheet)
        layout.addWidget(self.title)

        self.title.setToolTip("The title of the story. This is also currently used as the filename when saving or exporting the story.")

        summary = QWidget()
        summary_layout = QFormLayout()
        self.summary = TokenizedTextEdit()
        self.summary.setPlaceholderText("Background Information")
        summary_layout.addRow("Background\nInformation", self.summary)
        summary.setLayout(summary_layout)
        summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        summary.setMaximumHeight(100)
        layout.addWidget(summary)

        summary.setToolTip("Background information is always added at the top of prompts sent to the LLM.")

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)

        self.scrollContent = QWidget(self.scrollArea)
        self.chapterLayout = QVBoxLayout(self.scrollContent)
        self.scrollContent.setLayout(self.chapterLayout)
        self.scrollArea.setWidget(self.scrollContent)
        self.scrollArea.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout.addWidget(self.scrollArea)

        self.buttonsLayout = QHBoxLayout()

        self.new_chapter_button = QPushButton("Add a new Chapter")
        self.new_chapter_button.clicked.connect(self.addChapter)
        self.buttonsLayout.addWidget(self.new_chapter_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.saveStory)
        self.buttonsLayout.addWidget(self.save_button)
        self.save_button.setToolTip("Because the programmer is lazy this currently just saves the current story as a file called title.json")

        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.loadStory)
        self.buttonsLayout.addWidget(self.load_button)

        self.export_button = QPushButton("Export Text")
        self.export_button.clicked.connect(self.exportStory)
        self.buttonsLayout.addWidget(self.export_button)
        self.export_button.setToolTip('Exports the "end product" parts of the story as a text file. Summaries are removed.')

        layout.addLayout(self.buttonsLayout)

        self.setLayout(layout)

    def addChapter(self):
        Chapter(self)

    def loadStory(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load story", "", "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        json_data = load_story_data(file_path)
        if json_data is None:
            return
        self.summary.setPlainTextAndTokens(json_data.get("summary", ""), int(json_data.get("summaryTokens", -1)))
        self.title.setText(json_data["title"])
        _clear_layout(self.chapterLayout)
        for chapter_data in json_data["chapters"]:
            Chapter(self, chapter_data)

    def saveStory(self):
        filename = sanitize_filename(self.title.text())
        save_story_data(filename + ".json", self)

    def exportStory(self):
        filename = sanitize_filename(self.title.text())
        export_story_text(filename + ".txt", self)
