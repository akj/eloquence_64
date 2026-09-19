import builtins
import importlib
import queue
import sys
import threading
import types
import unittest
from unittest import mock


class _FakeProgressDialog:
	def __init__(self, title, message, maximum, parent, style):
		self.updates = []
		self.cancel_pressed = False
		self.destroyed = False

	def Pulse(self, message):
		self.updates.append((None, message))

	def Update(self, percent, message):
		self.updates.append((percent, message))

	def WasCancelled(self):
		return self.cancel_pressed

	def Bind(self, event, handler, source):
		self.on_timer = handler

	def Destroy(self):
		self.destroyed = True


class _FakeTimer:
	def __init__(self, owner):
		self.running = False

	def Start(self, interval):
		self.running = True

	def Stop(self):
		self.running = False


class _FakeWx(types.ModuleType):
	"""Stands in for wx. CallAfter queues calls, and the test drains the queue as the UI thread would."""

	PD_APP_MODAL = 1
	PD_CAN_ABORT = 2
	EVT_TIMER = object()
	ProgressDialog = _FakeProgressDialog
	Timer = _FakeTimer

	def __init__(self):
		super().__init__("wx")
		self.calls = queue.Queue()

	def CallAfter(self, function, *args):
		self.calls.put((function, args))

	def run_next_call(self):
		function, args = self.calls.get(timeout=5)
		function(*args)


class BackgroundWorkTests(unittest.TestCase):
	def setUp(self):
		self.wx = _FakeWx()
		stubs = {"wx": self.wx, "addonHandler": types.SimpleNamespace(initTranslation=lambda: None)}
		patcher = mock.patch.dict(sys.modules, stubs)
		patcher.start()
		self.addCleanup(patcher.stop)
		translation = mock.patch.object(builtins, "_", lambda text: text, create=True)
		translation.start()
		self.addCleanup(translation.stop)
		sys.modules.pop("addon.synthDrivers._background_work", None)
		self.module = importlib.import_module("addon.synthDrivers._background_work")
		self.addCleanup(sys.modules.pop, "addon.synthDrivers._background_work", None)
		self.done = []
		self.errors = []

	def start(self, work, **kwargs):
		return self.module.BackgroundWork(
			object(), "title", "message", work, self.done.append, self.errors.append, **kwargs
		)

	def test_work_runs_on_another_thread_and_result_returns_through_call_after(self):
		work_threads = []

		def work(is_cancelled, report):
			work_threads.append(threading.current_thread())
			report(40, "forty percent")
			return "result"

		background = self.start(work)
		self.assertEqual(self.done, [], "the constructor must not wait for the work")

		self.wx.run_next_call()
		self.assertEqual(background._dialog.updates[-1], (40, "forty percent"))
		self.assertEqual(self.done, [])

		self.wx.run_next_call()
		self.assertEqual(self.done, ["result"])
		self.assertEqual(self.errors, [])
		self.assertIsNot(work_threads[0], threading.current_thread())
		self.assertTrue(background._dialog.destroyed)
		self.assertFalse(background._timer.running)

	def test_exception_from_work_reaches_on_error(self):
		error = OSError("network down")

		def work(is_cancelled, report):
			raise error

		self.start(work)
		self.wx.run_next_call()

		self.assertEqual(self.errors, [error])
		self.assertEqual(self.done, [])

	def test_cancel_button_is_seen_by_blocked_work(self):
		saw_cancel = threading.Event()

		def work(is_cancelled, report):
			while not is_cancelled():
				saw_cancel.wait(0.01)
			return "stopped early"

		background = self.start(work, doneMessage="close me")
		background._dialog.cancel_pressed = True
		background._dialog.on_timer(None)
		self.wx.run_next_call()

		self.assertEqual(self.done, ["stopped early"])
		self.assertEqual(background._dialog.updates[-1], (None, "Cancelling..."))

	def test_done_message_holds_the_dialog_at_completion(self):
		background = self.start(lambda is_cancelled, report: "path", doneMessage="close me")
		self.wx.run_next_call()

		self.assertEqual(background._dialog.updates[-1], (100, "close me"))
		self.assertEqual(self.done, ["path"])


if __name__ == "__main__":
	unittest.main()
