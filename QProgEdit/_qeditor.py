#-*- coding:utf-8 -*-

"""
This file is part of QProgEdit.

QProgEdit is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

QProgEdit is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with QProgEdit.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
from PyQt4 import QtGui, QtCore
from PyQt4 import Qsci
from PyQt4.Qsci import QsciScintilla, QsciScintillaBase
from QProgEdit.py3 import *
from QProgEdit import QLexer, QColorScheme, QSymbolTreeWidgetItem, symbols, \
	validate, clean, _

class QEditor(QsciScintilla):

	"""
	desc:
		A single editor widget, which is embedded in a QProgEdit widget.
	"""

	invalidMarker = 8

	cursorRowChanged = QtCore.pyqtSignal(int, int) # (Old row, new row)
	focusLost = QtCore.pyqtSignal()
	focusReceived = QtCore.pyqtSignal()
	handlerButtonClicked = QtCore.pyqtSignal()

	def __init__(self, qProgEdit):

		"""
		desc:
			Constructor.

		arguments:
			qProgEdit:
				desc:	The parent QProgEdit.
				type:	QProgEdit
		"""

		super(QEditor, self).__init__(qProgEdit)
		self.setEolMode(self.EolUnix)
		self.setUtf8(True)
		self.qProgEdit = qProgEdit
		self.validationErrors = {}
		self.setLang()
		self.commentShortcut = QtGui.QShortcut(QtGui.QKeySequence(
			self.cfg.qProgEditCommentShortcut), self,
			context=QtCore.Qt.WidgetWithChildrenShortcut)
		self.uncommentShortcut = QtGui.QShortcut(QtGui.QKeySequence(
			self.cfg.qProgEditUncommentShortcut), self,
			context=QtCore.Qt.WidgetWithChildrenShortcut)
		self.commentShortcut.activated.connect(self.commentSelection)
		self.uncommentShortcut.activated.connect(self.uncommentSelection)
		self.applyCfg()
		self.linesChanged.connect(self.updateMarginWidth)
		self.selectionChanged.connect(self.highlightSelection)
		self.cursorPositionChanged.connect(self.cursorMoved)
		self.marginClicked.connect(self.onMarginClick)
		self.setMarginSensitivity(1, True)
		self.cursorRow = 0
		self.symbolTree = None
		self.symbolTreeWidgetItemClass = QSymbolTreeWidgetItem
		self._symbols = []

	@property
	def tabManager(self):
		return self.qProgEdit.tabManager

	@property
	def cfg(self):
		return self.qProgEdit.cfg

	@property
	def focusTab(self):
		return self.qProgEdit.focusTab

	@property
	def tabIndex(self):
		return self.qProgEdit.tabIndex

	def applyCfg(self):

		"""
		desc:
			Applies the configuration.
		"""

		if hasattr(QColorScheme, self.cfg.qProgEditColorScheme):
			colorScheme = getattr(QColorScheme, \
				self.cfg.qProgEditColorScheme)
		else:
			colorScheme = QColorScheme.Default
		# Define indicator for selection matching
		self.indicatorDefine(self.INDIC_STRAIGHTBOX, 0)
		indicatorColor = QtGui.QColor(colorScheme[u'Highlight'])
		indicatorColor.setAlpha(64)
		self.setIndicatorForegroundColor(indicatorColor, 0)
		self.markerDefine(QsciScintilla.RightArrow, self.invalidMarker)
		self.setMarkerBackgroundColor(QtGui.QColor(
			colorScheme[u'Invalid']), self.invalidMarker)
		self.setMarkerForegroundColor(QtGui.QColor(
			colorScheme[u'Invalid']), self.invalidMarker)
		self.commentShortcut.setKey(QtGui.QKeySequence(
			self.cfg.qProgEditCommentShortcut))
		self.uncommentShortcut.setKey(QtGui.QKeySequence(
			self.cfg.qProgEditUncommentShortcut))
		font = QtGui.QFont(self.cfg.qProgEditFontFamily,
			self.cfg.qProgEditFontSize)
		self.setFont(font)
		self.setTabWidth(self.cfg.qProgEditTabWidth)
		self.setAutoIndent(self.cfg.qProgEditAutoIndent)
		self.setEolVisibility(self.cfg.qProgEditShowEol)
		self.setIndentationGuides(self.cfg.qProgEditShowIndent)
		self.setCaretLineVisible(
			self.cfg.qProgEditHighlightCurrentLine)
		if self.cfg.qProgEditShowFolding:
			self.setFolding(QsciScintilla.PlainFoldStyle)
		else:
			self.setFolding(QsciScintilla.NoFoldStyle)
		self.setMarginLineNumbers(0, self.cfg.qProgEditLineNumbers)
		if u'Fold margin' in colorScheme:
			color = QtGui.QColor(colorScheme[u'Fold margin'])
			self.setFoldMarginColors(color, color)
		if self.cfg.qProgEditShowWhitespace:
			self.setWhitespaceVisibility(QsciScintilla.WsVisible)
		else:
			self.setWhitespaceVisibility(QsciScintilla.WsInvisible)
		if self.cfg.qProgEditWordWrap:
			self.setWrapMode(QsciScintilla.WrapWord)
		else:
			self.setWrapMode(QsciScintilla.WrapNone)
		if self.cfg.qProgEditWordWrapMarker != None:
			self.setEdgeColumn(self.cfg.qProgEditWordWrapMarker)
			self.setEdgeMode(QsciScintilla.EdgeLine)
		else:
			self.setEdgeMode(QsciScintilla.EdgeNone)
		if self.cfg.qProgEditAutoComplete:
			self.setAutoCompletionSource(QsciScintilla.AcsAll)
		else:
			self.setAutoCompletionSource(QsciScintilla.AcsNone)
		if self.cfg.qProgEditHighlightMatchingBrackets:
			self.setBraceMatching(QsciScintilla.StrictBraceMatch)
		else:
			self.setBraceMatching(QsciScintilla.NoBraceMatch)
		self.setLang(self.lang())
		self.cfgVersion = self.cfg.version()

	def commentSelection(self):

		"""
		desc:
			Comments out the currently selected text.
		"""

		self.beginUndoAction()
		cl, ci = self.getCursorPosition()
		if not self.hasSelectedText():
			select = False
			# If there is no selection, use the current line
			fl = self.getCursorPosition()[0]
			tl = fl
			fi = 0
			ti = self.lineLength(tl)
		else:
			select = True
			fl, fi, tl, ti = self.getSelection()
			if fi > 0:
				fi += 1
			ti += 1
		for l in range(fl, tl+1):
			self.insertAt(u'#', l, 0)
		ci += 1
		self.setCursorPosition(cl, ci)
		if select:
			self.setSelection(fl, fi, tl, ti)
		self.endUndoAction()

	def cursorMoved(self):

		"""
		desc:
			Is called whenever the cursor moves, checks whether the cursor has
			jumped from one line to the next, and, if so, calls the relevant
			functions.
		"""

		row, col = self.getCursorPosition()
		if self.cursorRow != row:
			self.validate()
			self.updateSymbolTree()
			self.cursorRowChanged.emit(self.cursorRow, row)
			self.tabManager.cursorRowChanged.emit(self.tabIndex(),
				self.cursorRow, row)
		self.cursorRow = row

	def focusOutEvent(self, e):

		"""
		desc:
			Called when the editor loses focus.
		"""

		if e.reason() == QtCore.Qt.PopupFocusReason:
			e.ignore()
			return
		self.validate()
		self.updateSymbolTree()
		if self.isModified():
			self.setModified(False)
		super(QEditor, self).focusOutEvent(e)
		self.focusLost.emit()
		self.tabManager.focusLost.emit(self.tabIndex())

	def focusInEvent(self, e):

		"""
		desc:
			Called when the editor receives focus.
		"""

		if self.tabManager.cfg.version() != self.cfgVersion:
			self.applyCfg()
		super(QEditor, self).focusInEvent(e)
		self.focusReceived.emit()
		self.tabManager.focusReceived.emit(self.tabIndex())

	def highlightSelection(self):

		"""
		desc:
			Highlights all parts of the text that match the current selection.
		"""

		text = QtCore.QString(self.text())
		selection = self.selectedText()
		length = len(selection)
		self.clearIndicatorRange(0, 0, self.lines(), 0, 0)
		if length < 3 or u'\n' in selection:
			return
		self.qProgEdit.find.setFindText(selection)
		indexList = []
		i = -1
		line, index = self.getCursorPosition()
		currentPos = self.positionFromLineIndex(line, index)
		while True:
			i = text.indexOf(selection, i+1)
			if i < 0:
				break
			if i <= currentPos and i+length >= currentPos:
				continue
			line, index = self.lineIndexFromPosition(i)
			self.fillIndicatorRange(line, index, line, index+length, 0)

	def keyPressEvent(self, event):

		"""
		desc:
			Intercepts certain keypress events to implement custom copy-pasting
			and zooming.

		arguments:
			event:
				type:	QKeyPressEvent
		"""

		key = event.key()
		ctrl = event.modifiers() & QtCore.Qt.ControlModifier
		shift = event.modifiers() & QtCore.Qt.ShiftModifier
		# Zoom in/out
		if ((key == QtCore.Qt.Key_Plus) and ctrl) \
			or ((key == QtCore.Qt.Key_Equal) and shift and ctrl):
			self.zoomIn()
			event.accept()
		elif (key == QtCore.Qt.Key_Minus) and ctrl:
			self.zoomOut()
			event.accept()
		elif (key == QtCore.Qt.Key_V) and ctrl:
			self.paste()
			event.accept()
		else:
			QsciScintilla.keyPressEvent(self, event)

	def onMarginClick(self, margin, line, state):

		"""
		desc:
			Shows validation errors when the margin symbol is clicked.

		arguments:
			margin:
				desc:	The margin number.
				type:	int
			line:
				desc:	The line number.
				type:	int
			state:
				desc:	The keyboard state.
				type:	int
		"""

		if margin != 1:
			return
		if line in self.validationErrors:
			err = self.validationErrors[line]
			QtGui.QToolTip.showText(QtGui.QCursor().pos(), err)

	def uncommentSelection(self):

		"""
		desc:
			Uncomments the currently selected text.
		"""

		self.beginUndoAction()
		cl, ci = self.getCursorPosition()
		if not self.hasSelectedText():
			select = False
			# If there is no selection, use the current line
			fl = self.getCursorPosition()[0]
			tl = fl
			fi = 0
			ti = self.lineLength(tl)-1
		else:
			select = True
			fl, fi, tl, ti = self.getSelection()
		stripped = False
		for l in range(fl, tl+1):
			l = self.setSelection(l, 0, l, self.lineLength(l))
			s = self.selectedText()
			_s = s.trimmed()
			if len(_s) == 0 or _s[0] != u'#':
				continue
			stripped = True
			i = s.indexOf(u'#')
			s = s.remove(i, 1)
			self.replaceSelectedText(s)
		# If a comment character has been stripped, we need to jump back one
		# position, but not below 0
		if stripped:
			ci = max(0, ci-1)
			ti = max(0, ti-1)
		self.setCursorPosition(cl, ci)
		if select:
			self.setSelection(fl, fi, tl, ti)
		self.endUndoAction()

	def lang(self):

		"""
		returns:
			desc:	The language of the editor.
			type:	unicode
		"""

		return self._lang

	def paste(self):

		"""
		desc:
			Re-implements the paste method to allow modification of paste
			content.
		"""

		text = unicode(QtGui.QApplication.clipboard().text())
		if hasattr(clean, self.lang().lower()):
			msg, cleanText = getattr(clean, self.lang().lower())(text)
			if msg != None:
				resp = QtGui.QMessageBox.question(self, _(u'Pasting content'), \
					msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
				if resp == QtGui.QMessageBox.Yes:
					text = cleanText
		self.replaceSelectedText(text)

	def setLang(self, lang=u'text'):

		"""
		desc:
			Sets the editor language.

		keywords:
			lang:
				desc:	A language, used to select a lexer for syntax
						highlighting, validation, cleaning, etc.
						if an appropriate lexer isn't found, no error is
						generated, but syntax highlighting is disabled. For a
						list of available lexers, refer to the QsciScintilla
						documentation.
		"""

		self._lexer = QLexer(self, lang=lang,
			colorScheme=self.cfg.qProgEditColorScheme)
		self._lang = lang
		self.SendScintilla(QsciScintillaBase.SCI_CLEARDOCUMENTSTYLE)
		self.setLexer(self._lexer)
		self.validate()

	def setSymbolTree(self, symbolTree,
		symbolTreeWidgetItemClass=QSymbolTreeWidgetItem):

		"""
		desc:
			Sets the symbol-tree widget.

		arguments:
			symbolTree:
				desc:	A symbol-tree widget.
				type:	QTreeWidgetItem

		keywords:
			symbolTreeWidgetItemClass:
				desc:	The class to use for symbol-tree widgets. This should
						derive from QSymbolTreeWidgetItem.
				type:	type
		"""

		self.symbolTree = symbolTree
		self.symbolTreeWidgetItemClass = symbolTreeWidgetItemClass
		self._symbols = []
		self.updateSymbolTree()

	def setText(self, text):

		"""
		desc:
			Sets the editor contents.

		arguments:
			text:
				desc:	A text string. This can be a str object, which is
						assumed to be in utf-8 encoding, a Unicode object, or a
						QString.
				type:	[str, unicode, QString]
		"""

		if isinstance(text, str) and hasattr(text, u'decode'):
			text = text.decode(u'utf-8')
		elif not isinstance(text, unicode) and not isinstance(text, \
			QtCore.QString):
			raise Exception(u'Expecting a str, unicode, or QString object')
		super(QEditor, self).setText(text)
		self.setModified(False)
		self.updateSymbolTree()
		self.validate()

	def text(self):

		"""
		desc:
			Retrieves the editor contents.

		returns:
			desc:	The editor contents.
			type:	unicode
		"""

		return unicode(super(QEditor, self).text())

	def updateMarginWidth(self):

		"""
		desc:
			Updates the width of the margin containing the line numbers.
		"""

		self.setMarginWidth(0, u' %s' % self.lines())

	def updateSymbolTree(self):

		"""
		desc:
			Updates the symbol tree, if any has been specified and a symbol
			parser is available for the langauage.
		"""

		if self.symbolTree == None:
			return
		_symbols = self.symbols()
		if _symbols == self._symbols:
			return
		self.symbolTree.takeChildren()
		for lineNo, _type, name, argSpec in self.symbols():
			self.symbolTree.addChild(self.symbolTreeWidgetItemClass(self,
				lineNo, _type, name, argSpec))
		self._symbols = _symbols

	def symbols(self):

		"""
		desc:
			Returns an up-to-date list of symbols.

		returns:
			desc:	A list of symbols.
			type:	list
		"""

		if not hasattr(symbols, self.lang().lower()):
			return []
		parser = getattr(symbols, self.lang().lower())
		return parser(self.text())

	def validate(self):

		"""
		desc:
			Validates the content.
		"""

		self.highlightSelection()
		cl = self.getCursorPosition()[0]
		validateCurrentLine = cl in self.validationErrors
		self.validationErrors = {}
		self.markerDeleteAll()
		if not self.cfg.qProgEditValidate or not hasattr(validate, \
			self.lang().lower()):
			return
		validator = getattr(validate, self.lang().lower())
		for l, s in validator(self.text()):
			# Do not validate negative positions or the current line, unless the
			# current line already had a negative validation before.
			if l < 0 or (not validateCurrentLine and l == cl):
				continue
			self.validationErrors[l] = s
			self.markerAdd(l, self.invalidMarker)

	def wheelEvent(self, event):

		"""
		desc:
			Implements scroll-to-zoom functionality.

		arguments:
			event:
				type:	QWheelEvent
		"""

		if QtCore.Qt.ControlModifier == event.modifiers():
			event.ignore()
			if event.delta() > 0:
				self.zoomIn()
			else:
				self.zoomOut()
		else:
			super(QEditor, self).wheelEvent(event)
