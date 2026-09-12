import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

URLS = [
    "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html",
    "https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html",
    "https://docs.ansible.com/ansible/latest/module_plugin_guide/modules_intro.html",
]

async def main():
    results = []

    # Configuration du navigateur headless : verbose=True affiche les logs
    # détaillés du navigateur pendant le scraping (utile pour déboguer).
    browser_config = BrowserConfig(verbose=True)

    # Configuration du traitement de chaque page : exclude_external_links=True
    # retire les liens pointant vers d'autres sites du markdown renvoyé.
    # Ici la doc Ansible est déjà propre, donc sans effet visible dans notre cas,
    # mais utile en général pour ne garder que le contenu pertinent.
    run_config = CrawlerRunConfig(exclude_external_links=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in URLS:
            print(f"Crawling: {url}")
            result = await crawler.arun(url=url, config=run_config)
            results.append({
                "url": url,
                "title": result.metadata.get("title"),
                "markdown": result.markdown
            })

    # Le fichier généré est ensuite déplacé vers data/raw/ansible_docs.json,
    # emplacement standard du projet pour les données brutes collectées.
    with open("ansible_docs.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{len(results)} pages collectées, sauvegardées dans ansible_docs.json")

asyncio.run(main())