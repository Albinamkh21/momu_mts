# tests/e2e/test_frontend.py
from playwright.sync_api import Page, expect

def test_frontend_opens_and_shows_new_track_button(page: Page):

    page.goto("http://momu_ui:5173/")
    
   
    button = page.get_by_role("button", name="➕ Новый трек")
    
    # Способ Б (альтернативный): поиск через CSS-класс, если эмодзи вдруг мешает
    # button = page.locator("button.btn-primary", has_text="Новый трек")
    

    expect(button).to_be_visible()