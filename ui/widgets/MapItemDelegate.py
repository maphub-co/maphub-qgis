from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PyQt5.QtGui import QIcon, QBrush, QColor

# Define a custom role for storing status indicator data
STATUS_INDICATOR_ROLE = Qt.UserRole + 100
# Define a custom role for identifying the project folder
PROJECT_FOLDER_ROLE = Qt.UserRole + 101

class MapItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for painting map items with status indicators.
    
    This delegate extends the standard item painting to include status
    indicators at the end of the item text, rather than as child nodes.
    """
    
    def __init__(self, parent=None):
        """Initialize the delegate."""
        super(MapItemDelegate, self).__init__(parent)
        
    def paint(self, painter, option, index):
        """
        Paint the item with a status indicator if available and highlight if it's the project folder.
        
        Args:
            painter: The QPainter to use for drawing
            option: The style options for the item
            index: The model index of the item
        """
        # Check if this item is the project folder
        is_project_folder = index.data(PROJECT_FOLDER_ROLE)
        
        # If this is the project folder, modify the style option to highlight it
        if is_project_folder:
            # Create a copy of the style option to modify
            highlight_option = QStyleOptionViewItem(option)
            
            # Set a background color for highlighting (light blue)
            highlight_option.backgroundBrush = QBrush(QColor(173, 216, 230, 100))
            
            # Paint the item with the modified style option
            super(MapItemDelegate, self).paint(painter, highlight_option, index)
        else:
            # Paint the standard item using the parent class
            super(MapItemDelegate, self).paint(painter, option, index)
        
        # Check if this item has a status indicator
        status_data = index.data(STATUS_INDICATOR_ROLE)
        if not status_data:
            return
            
        # Extract status information
        icon_path = status_data.get('icon_path')
        if not icon_path:
            return
            
        # Create icon from path
        icon = QIcon(icon_path)
        if icon.isNull():
            return
            
        # Calculate position for the status icon (right-aligned)
        icon_size = 16  # Fixed size for status icons
        icon_rect = QRect(
            option.rect.right() - icon_size - 5,  # 5 pixels padding from right
            option.rect.top() + (option.rect.height() - icon_size) // 2,  # Vertically centered
            icon_size,
            icon_size
        )
        
        # Draw the icon
        icon.paint(painter, icon_rect)
        
    def sizeHint(self, option, index):
        """
        Calculate the size hint for the item, accounting for the status indicator.
        
        Args:
            option: The style options for the item
            index: The model index of the item
            
        Returns:
            QSize: The recommended size for the item
        """
        # Get the standard size hint
        size = super(MapItemDelegate, self).sizeHint(option, index)
        
        # Check if this item has a status indicator
        status_data = index.data(STATUS_INDICATOR_ROLE)
        if status_data:
            # Add space for the status icon (16px) plus padding (5px)
            size.setWidth(size.width() + 21)
            
        return size