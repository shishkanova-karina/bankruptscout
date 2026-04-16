"""Scrapy-элементы для пауков ЕФРСБ и КАД."""

import scrapy


class FedresursInsolvencyItem(scrapy.Item):
    inn = scrapy.Field()
    case_number = scrapy.Field()
    last_event_date = scrapy.Field()
    error = scrapy.Field()


class KadDocumentItem(scrapy.Item):
    case_number = scrapy.Field()
    last_event_date = scrapy.Field()
    document_name = scrapy.Field()
    document_url = scrapy.Field()
    error = scrapy.Field()


class FedresursFinishedItem(scrapy.Item):
    """Сигнал завершения обработки ИНН на стороне ЕФРСБ (для resume)."""

    inn = scrapy.Field()


class KadFinishedItem(scrapy.Item):
    """Сигнал завершения обработки номера дела на стороне КАД."""

    case_number = scrapy.Field()
