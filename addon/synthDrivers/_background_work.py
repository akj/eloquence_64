"""Keeps NVDA's UI thread free while the settings panel downloads or writes files."""

import threading

import addonHandler
import wx

addonHandler.initTranslation()


class BackgroundWork:
	"""Runs blocking work outside NVDA's UI thread behind a cancellable progress dialog.

	work(is_cancelled, report) runs on a worker thread. report(percent, message) updates the dialog, and
	a percent of None shows indeterminate progress. Cancelling does not interrupt work; work is expected
	to poll is_cancelled and stop. When work ends, onDone(result) or onError(exception) runs on the UI
	thread after the dialog has closed. With doneMessage, the dialog first stays open at 100% showing
	that message until the user closes it.
	"""

	_POLL_INTERVAL_MS = 100

	def __init__(self, parent, title, message, work, onDone, onError, doneMessage=None):
		self._work = work
		self._onDone = onDone
		self._onError = onError
		self._doneMessage = doneMessage
		self._cancelled = threading.Event()
		self._dialog = wx.ProgressDialog(
			title, message, maximum=100, parent=parent, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT
		)
		self._dialog.Pulse(message)
		self._timer = wx.Timer(self._dialog)
		self._dialog.Bind(wx.EVT_TIMER, self._onPoll, self._timer)
		self._timer.Start(self._POLL_INTERVAL_MS)
		threading.Thread(target=self._run, name="EloquenceBackgroundWork", daemon=True).start()

	def _run(self):
		try:
			result, error = self._work(self._cancelled.is_set, self._report), None
		except Exception as e:
			result, error = None, e
		wx.CallAfter(self._finish, result, error)

	def _report(self, percent, message):
		wx.CallAfter(self._update, percent, message)

	def _update(self, percent, message):
		if self._cancelled.is_set():
			return
		if percent is None:
			self._dialog.Pulse(message)
		else:
			self._dialog.Update(percent, message)

	def _onPoll(self, evt):
		if self._dialog.WasCancelled() and not self._cancelled.is_set():
			self._cancelled.set()
			# Translators: Message of a progress dialog after the user pressed Cancel
			self._dialog.Pulse(_("Cancelling..."))

	def _finish(self, result, error):
		self._timer.Stop()
		# NVDA may have exited while the worker was running, taking the settings dialog and this one with it.
		if not self._dialog:
			return
		if error is None and self._doneMessage and not self._cancelled.is_set():
			self._dialog.Update(100, self._doneMessage)
		self._dialog.Destroy()
		if error is None:
			self._onDone(result)
		else:
			self._onError(error)
