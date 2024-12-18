import cv2
import numpy as np
import pytesseract
from spellchecker import SpellChecker
from collections import Counter

# Path to Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Adjust path if needed

# Initialize the spell checker
spell = SpellChecker()

# Global variables for trackbar values
gaussian_blur_value = 5  # Default Gaussian blur value (should be odd)
sharpen_kernel_value = 1  # Default sharpening kernel value (1 to 3)
invert_colors = False      # Flag for inverting colors
denoise_h = 30            # Denoising parameter
morph_kernel_size = 2     # Size for morphological operations
spell_check_enabled = True  # Flag for enabling/disabling spell check
use_preprocessed_image = True  # Flag to choose between original or preprocessed image for OCR

def perform_ocr(image):
    """Perform OCR on the preprocessed image using LSTM engine."""
    custom_config = r'--oem 3 --psm 6'  # Use OEM 3 for LSTM engine
    return pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)

def sharpen_image(image, kernel_value):
    """Sharpen the image to enhance text clarity."""
    kernel = np.array([[0, -1, 0], [-1, 5 + kernel_value, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, kernel)

def correct_spelling(text):
    """Correct spelling of detected text using a spell checker."""
    words = text.split()
    corrected = []
    
    for word in words:
        # Get the best candidate for each word
        candidates = spell.candidates(word)
        # Select the first candidate if there are any candidates
        corrected_word = next(iter(candidates), word) if candidates else word
        corrected.append(corrected_word)
    
    return ' '.join(corrected)

def preprocess_image(frame):
    """Preprocess the image for better OCR results."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Convert to grayscale
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))  # Create CLAHE object
    contrast_enhanced = clahe.apply(gray)  # Apply CLAHE to the grayscale image
    sharpened = sharpen_image(contrast_enhanced, sharpen_kernel_value)  # Sharpen the image
    denoised = cv2.fastNlMeansDenoising(sharpened, None, h=denoise_h, templateWindowSize=7, searchWindowSize=21)  # Denoising
    blurred = cv2.GaussianBlur(denoised, (gaussian_blur_value, gaussian_blur_value), 0)  # Apply Gaussian Blur
    
    # Adaptive Thresholding
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)
    
    # Morphological Operations
    kernel = np.ones((morph_kernel_size, morph_kernel_size), np.uint8)
    morph_open = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    if invert_colors:
        inverted = cv2.bitwise_not(morph_open)  # Invert the image colors
        return inverted  # Return the inverted image directly
    return morph_open  # Return the final processed image

def draw_boxes(frame, boxes, dynamic_threshold):
    """Draw bounding boxes around detected text and collect detected text."""
    detected_text = ""
    n_boxes = len(boxes['level'])
    
    for i in range(n_boxes):
        if int(boxes['conf'][i]) > dynamic_threshold:
            (x, y, w, h) = (boxes['left'][i], boxes['top'][i], boxes['width'][i], boxes['height'][i])
            cv2.rectangle(frame, (x, y), (x + w, y + h), (50, 50, 50), 2)
            detected_text += boxes['text'][i] + " "
    
    return detected_text.strip()

def update_gaussian_blur(value):
    """Update Gaussian blur value from trackbar.""" 
    global gaussian_blur_value
    gaussian_blur_value = value if value % 2 == 1 else value + 1  # Ensure it's odd

def update_sharpen_kernel(value):
    """Update sharpening kernel value from trackbar.""" 
    global sharpen_kernel_value
    sharpen_kernel_value = value

def update_denoise_h(value):
    """Update denoising parameter from trackbar."""
    global denoise_h
    denoise_h = value

def update_morph_kernel(value):
    """Update morphological kernel size from trackbar."""
    global morph_kernel_size
    morph_kernel_size = value if value % 2 == 1 else value + 1  # Ensure it's odd

def toggle_invert_colors(value):
    """Toggle color inversion based on trackbar.""" 
    global invert_colors
    invert_colors = bool(value)

def toggle_spell_check(value):
    """Toggle spell checking based on trackbar."""
    global spell_check_enabled
    spell_check_enabled = bool(value)

def toggle_image_source(value):
    """Toggle between original and preprocessed image for OCR."""
    global use_preprocessed_image
    use_preprocessed_image = bool(value)

def update_zoom(value):
    """Update zoom level from trackbar."""
    global zoom_level
    zoom_level = max(1, value)  # Ensure minimum zoom level is 1


def main():
    """Main function to capture video and perform OCR.""" 
    # Initialize video capture
    cap = cv2.VideoCapture(1)

    # Set camera resolution to a lower value for better performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: Could not open video device.")
        return

    # Create a window for adjustments
    cv2.namedWindow("Settings")
    cv2.createTrackbar("Zoom Level", "Settings", 1, 5, update_zoom)
    cv2.createTrackbar("Gaussian Blur", "Settings", 1, 20, update_gaussian_blur)
    cv2.createTrackbar("Sharpen Kernel", "Settings", 1, 5, update_sharpen_kernel)
    cv2.createTrackbar("Denoise Parameter", "Settings", 10, 100, update_denoise_h)
    cv2.createTrackbar("Morph Kernel Size", "Settings", 2, 10, update_morph_kernel)
    cv2.createTrackbar("Invert Colors", "Settings", 0, 1, toggle_invert_colors)
    cv2.createTrackbar("Spell Check", "Settings", 1, 1, toggle_spell_check)
    cv2.createTrackbar("Use Preprocessed", "Settings", 1, 1, toggle_image_source)

    word_counter = Counter()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
        
        # Resize frame to reduce processing load
        frame = cv2.resize(frame, (640, 480))

        # Apply zoom effect
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2
        radius_x, radius_y = w // (2 * zoom_level), h // (2 * zoom_level)

        # Crop and resize to create the zoom effect
        cropped_frame = frame[center_y - radius_y:center_y + radius_y, center_x - radius_x:center_x + radius_x]
        zoomed_frame = cv2.resize(cropped_frame, (w, h))

        # Perform preprocessing on zoomed frame
        preprocessed_frame = preprocess_image(zoomed_frame)

        # Choose between original or preprocessed for OCR
        ocr_frame = preprocessed_frame if use_preprocessed_image else zoomed_frame

        # Perform OCR
        boxes = perform_ocr(ocr_frame)

        # Compute dynamic threshold
        confidences = np.array(boxes['conf'])
        dynamic_threshold = np.percentile(confidences[confidences > 0], 75) if np.any(confidences > 0) else 0

        detected_text = draw_boxes(zoomed_frame, boxes, dynamic_threshold)

        if detected_text:
            corrected_text = detected_text
            if spell_check_enabled:
                corrected_text = correct_spelling(detected_text)

            print("Detected Text:", corrected_text)

            for word in corrected_text.split():
                word_counter[word] += 1

            expected_text = analyze_expected_words(word_counter)
            print("Expected Text:", expected_text)

            cv2.putText(zoomed_frame, f"Detected: {corrected_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 50, 50), 2)
            cv2.putText(zoomed_frame, f"Expected: {expected_text}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Original Live Feed", zoomed_frame)
        cv2.imshow("Preprocessed for OCR", preprocessed_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    
def analyze_expected_words(word_counter):
    """Analyze the word counts and find the most probable expected words.""" 
    most_common = word_counter.most_common(2)  # Get top 2 common words
    expected_text = []

    # Combine high-frequency words to form expected phrases
    for word, count in most_common:
        expected_text.append(word)

    return ' '.join(expected_text)

if __name__ == "__main__":
    main()
