from odoo import models, fields, api
import logging
from functools import lru_cache
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    from googletrans import Translator
except ImportError:
    Translator = None
    _logger.warning("googletrans not installed. Install via pip if needed.")

class TranslationMixin(models.AbstractModel):
    _name = 'translation.mixin'
    _description = 'Generic Translation Mixin for Odoo Field Values'

    language_id = fields.Many2one(
        'res.lang',
        string='Language',
        domain=[('active', '=', True)],
        default=lambda self: self.env['res.lang'].search(
            [('code', '=', self.env.user.lang or 'en_US')], limit=1
        ),
        help="Target language for automatic field translation."
    )

    def _get_translatable_fields(self):
        allowed_types = (fields.Char, fields.Text, fields.Html, fields.Selection)
        return [
            field_name for field_name, field in self._fields.items()
            if getattr(field, 'translate', False) and isinstance(field, allowed_types)
        ]

    def _get_language_code(self, user_lang=None):
        return self.language_id.code if self.language_id else (user_lang or self.env.user.lang or 'en_US')

    @lru_cache(maxsize=5000)
    def _translate_text_cached(self, text, lang_code):
        if not text or not Translator:
            return text
        try:
            translator = Translator()
            start_time = datetime.now()
            translated = translator.translate(text, dest=lang_code.split('_')[0]).text
            duration = (datetime.now() - start_time).total_seconds()
            _logger.debug(f"Translated '{text}' to '{lang_code}' in {duration} seconds")
            return translated
        except Exception as e:
            _logger.warning(f"Translation failed for '{text}' to '{lang_code}': {e}")
            return text

    def _translate_text(self, texts, lang_code):
        if not texts or not Translator:
            return texts if isinstance(texts, list) else texts
        start_time = datetime.now()
        try:
            result = [
                self._translate_text_cached(text, lang_code) if not self._is_already_translated(text) else text
                for text in texts
            ] if isinstance(texts, list) else (
                self._translate_text_cached(texts, lang_code) if not self._is_already_translated(texts) else texts
            )
            duration = (datetime.now() - start_time).total_seconds()
            _logger.debug(f"Batch translation took {duration} seconds for {len(texts) if isinstance(texts, list) else 1} texts to {lang_code}")
            return result
        except Exception as e:
            _logger.warning(f"Batch translation failed for {len(texts) if isinstance(texts, list) else 1} texts to {lang_code}: {e}")
            return texts

    def _is_already_translated(self, text):
        """Check if text already contains a translation (e.g., 'original (translated)')."""
        return isinstance(text, str) and '(' in text and ')' in text and text.endswith(')')

    def _extract_original_text(self, text):
        """Extract the original (English) text from a translated string like 'original (translated)'."""
        if not isinstance(text, str):
            return text
        if self._is_already_translated(text):
            return text.split('(')[0].strip()
        return text

    @api.model_create_multi
    def create(self, vals_list):
        start_time = datetime.now()
        user_lang = self.env.user.lang or 'en_US'
        lang_record = self.env['res.lang'].search([('code', '=', user_lang)], limit=1)

        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            if not record.language_id or record.language_id.code != user_lang:
                record.language_id = lang_record

            lang_code = record._get_language_code(user_lang)
            if lang_code == 'en_US':
                continue

            translatable_fields = record._get_translatable_fields()
            # Only process fields present in vals
            texts = [
                vals[field]
                for field in translatable_fields
                if field in vals and vals[field] and not self._is_already_translated(vals[field])
            ]
            if not texts:
                continue

            translated_texts = record._translate_text(texts, lang_code)
            updates = {
                field: f"{vals[field]} ({translated})"
                for field, translated in zip(
                    [f for f in translatable_fields if f in vals],
                    translated_texts
                )
                if translated and translated != vals[field]
            }
            if updates:
                record.with_context(skip_translation=True).write(updates)

        duration = (datetime.now() - start_time).total_seconds()
        return records

    def write(self, vals):
        if self.env.context.get('skip_translation'):
            return super().write(vals)

        current_lang = self.env.context.get('lang', 'en_US')
        all_langs = self.env['res.lang'].search([('active', '=', True)])
        result = super().write(vals)

        for rec in self:
            translatable_fields = rec._get_translatable_fields()
            cleaned_vals = {}

            for field in translatable_fields:
                if field in vals and vals[field]:
                    # Assume user's input is the new English/base value
                    cleaned_vals[field] = self._extract_original_text(vals[field])

            if not cleaned_vals:
                continue

            # Force update base (English) field
            rec.with_context(skip_translation=True, lang='en_US').write(cleaned_vals)

            # Read back English text (to make sure translations use actual stored base)
            base_texts = [getattr(rec.with_context(lang='en_US'), field) for field in cleaned_vals]

            for lang in all_langs:
                if lang.code == 'en_US':
                    continue

                translated_texts = rec._translate_text(base_texts, lang.code)
                updates = {
                    field: f"{base} ({translated})"
                    for field, base, translated in zip(cleaned_vals, base_texts, translated_texts)
                    if translated and translated != base
                }
                if updates:
                    rec.with_context(skip_translation=True, lang=lang.code).write(updates)

        return result

    def read(self, fields=None, load='_classic_read'):
        start_time = datetime.now()
        records = super().read(fields=fields, load=load)
        user_lang = self.env.user.lang or 'en_US'
        lang_record = self.env['res.lang'].search([('code', '=', user_lang)], limit=1)
        translatable_fields = self._get_translatable_fields()

        all_texts = []
        text_indices = []
        for record in records:
            lang_code = lang_record.code if lang_record else user_lang
            if lang_code == 'en_US':
                continue

            for field in translatable_fields:
                if field in record and record[field] and not self._is_already_translated(record[field]):
                    all_texts.append(record[field])
                    text_indices.append((record, field))

        if all_texts:
            translated_texts = self._translate_text(all_texts, lang_code)
            for (record, field), translated in zip(text_indices, translated_texts):
                if translated and translated != record[field]:
                    record[field] = f"{record[field]} ({translated})"

        duration = (datetime.now() - start_time).total_seconds()
        _logger.info(f"Read operation took {duration} seconds for {len(records)} records with {len(all_texts)} translations")
        return records

    def _get_rec_name_field(self):
        """Return the field used for display names. Defaults to first translatable Char/Text field."""
        if hasattr(self, '_rec_name') and self._rec_name in self._fields:
            return self._rec_name

        for field_name in self._get_translatable_fields():
            if field_name in self._fields:
                return field_name

        # Fallback: return any char field or the first field available
        for field_name, field in self._fields.items():
            if isinstance(field, (fields.Char, fields.Text)):
                return field_name
        return 'id'

    def name_get(self):
        """
        Called by Odoo whenever the record has to render as text
        (dropdowns, kanbans, field widgets, etc.).
        Returns the name in the format 'Original (Translated)' when the user's
        language is not English, e.g., 'Safety (सुरक्षा)'.
        """
        results = []
        lang_code = self.env.context.get('lang') or self.env.user.lang or 'en_US'

        rec_name_field = self._get_rec_name_field()

        for rec in self:
            # Get the original value in English (base language)
            name_en = rec.with_context(lang='en_US')[rec_name_field]

            # Get the value in the active UI language
            name_lang = rec.with_context(lang=lang_code)[rec_name_field]

            # If the user's language is not English and the value isn't already in "Original (Translated)" format,
            # try to translate and combine the values
            if lang_code != 'en_US' and not rec._is_already_translated(name_lang):
                translated_text = rec._translate_text_cached(name_lang or name_en, lang_code)
                # Combine original and translated text in the format "Original (Translated)"
                display_text = f"{name_en} ({translated_text})" if translated_text else name_en
            else:
                # If the language is English or the value is already translated, use it as is
                display_text = name_lang or name_en

            # Final safeguard – ensure we always return something printable
            display_text = display_text or str(rec.id)
            results.append((rec.id, display_text))

        return results