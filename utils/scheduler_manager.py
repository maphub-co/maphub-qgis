from PyQt5.QtCore import QObject, QTimer

class SchedulerManager(QObject):
    """
    Generic scheduler for periodic execution of functions.
    
    This class provides functionality to:
    - Execute a specified function on demand
    - Schedule periodic execution of the function
    - Configure update intervals
    """
    
    def __init__(self, callback_function, update_interval_ms: int = None):
        """
        Initialize the scheduler manager.
        
        Args:
            callback_function: The function to execute when the timer triggers
        """
        super(SchedulerManager, self).__init__()
        self.callback_function = callback_function
        
        # Initialize timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._execute_callback)

        if update_interval_ms:
            self.update_interval = update_interval_ms
        else:
            # Default update interval (5 minutes = 300000 ms)
            self.update_interval = 300000
        
    def _execute_callback(self):
        """Execute the callback function."""
        if self.callback_function:
            self.callback_function()
            
    def execute_now(self):
        """Execute the callback function immediately."""
        self._execute_callback()
            
    def start_periodic_updates(self, interval_ms=None):
        """
        Start periodic execution of the callback function.
        
        Args:
            interval_ms: Update interval in milliseconds (default: use existing setting)
        """
        if interval_ms is not None:
            self.update_interval = interval_ms
            
        self.update_timer.start(self.update_interval)
        
    def stop_periodic_updates(self):
        """Stop periodic execution."""
        self.update_timer.stop()
        
    def set_update_interval(self, interval_ms):
        """
        Set the update interval.
        
        Args:
            interval_ms: Update interval in milliseconds
        """
        self.update_interval = interval_ms
        
        # Restart timer if it's running
        if self.update_timer.isActive():
            self.update_timer.start(self.update_interval)
            
    def is_active(self):
        """
        Check if the scheduler is active.
        
        Returns:
            bool: True if the scheduler is active, False otherwise
        """
        return self.update_timer.isActive()