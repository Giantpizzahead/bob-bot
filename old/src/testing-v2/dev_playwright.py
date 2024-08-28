import asyncio

from playwright.async_api import async_playwright


async def main():
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(record_video_dir="local/pw/videos")
        await context.tracing.start(screenshots=True, snapshots=True)
        page = await context.new_page()
        await page.goto("https://playwright.dev")
        print(await page.title())
        await context.tracing.stop(path="local/pw/trace.zip")
        await context.close()
        await browser.close()


asyncio.run(main())
