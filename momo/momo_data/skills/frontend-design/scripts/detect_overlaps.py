import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def detect_overlaps(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    absolute_path = f"file:///{os.path.abspath(file_path).replace(os.sep, '/')}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(absolute_path)

        # JS to find overlapping text elements
        # Focuses on SVG text (common in Plotly) and HTML text
        overlap_script = """
        () => {
            const elements = Array.from(document.querySelectorAll('text, span, div, p'));
            const overlaps = [];
            
            for (let i = 0; i < elements.length; i++) {
                const rect1 = elements[i].getBoundingClientRect();
                if (rect1.width === 0 || rect1.height === 0) continue;

                for (let j = i + 1; j < elements.length; j++) {
                    const rect2 = elements[j].getBoundingClientRect();
                    if (rect2.width === 0 || rect2.height === 0) continue;

                    const isRelated = elements[i].contains(elements[j]) || elements[j].contains(elements[i]);
                    if (isRelated) continue;

                    const overlap = !(
                        rect1.right < rect2.left || 
                        rect1.left > rect2.right || 
                        rect1.bottom < rect2.top || 
                        rect1.top > rect2.bottom
                    );

                    if (overlap) {
                        overlaps.push({
                            el1: { text: elements[i].innerText, rect: rect1 },
                            el2: { text: elements[j].innerText, rect: rect2 }
                        });
                    }
                }
            }
            return overlaps;
        }
        """
        
        results = await page.evaluate(overlap_script)
        await browser.close()
        return results

def main():
    if len(sys.argv) < 2:
        print("Usage: python detect_overlaps.py <path_to_html>")
        sys.exit(1)

    file_path = sys.argv[1]
    overlaps = asyncio.run(detect_overlaps(file_path))

    if not overlaps:
        print("Success: No overlapping text elements detected.")
    else:
        print(f"Failure: Detected {len(overlaps)} overlapping elements:\n")
        for i, o in enumerate(overlaps, 1):
            print(f"Overlap {i}:")
            print(f"  Element A: '{o['el1']['text']}' at {o['el1']['rect']}")
            print(f"  Element B: '{o['el2']['text']}' at {o['el2']['rect']}")
            print("-" * 40)

if __name__ == "__main__":
    main()
