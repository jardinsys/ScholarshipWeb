def safe_text(page, selector):
    try:
        return page.locator(selector).inner_text(timeout=3000)
    except:
        return None
