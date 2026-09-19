from django import forms

from .models import BespokeRequest


# =========================================================
# SHARED DATE INPUT
# =========================================================

class DateInput(forms.DateInput):
    input_type = "date"


# =========================================================
# BASE WIZARD FORM
# =========================================================

class BaseWizardForm(forms.ModelForm):
    """
    Adds consistent Bootstrap styling to every bespoke wizard form.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():

            # Checkboxes need Bootstrap's checkbox class
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"

            # Dropdowns
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"

            # Everything else
            else:
                existing_class = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (
                    f"{existing_class} form-control"
                ).strip()

            # Connect help text for accessibility
            if field.help_text:
                field.widget.attrs.setdefault(
                    "aria-describedby",
                    f"id_{field_name}_help",
                )


# =========================================================
# STEP 1
# THE CUSTOMER'S IDEA
# =========================================================

class BespokeIdeaForm(BaseWizardForm):

    class Meta:
        model = BespokeRequest

        fields = [
            "request_title",
            "item_type",
            "description",
            "inspiration_source",
        ]

        labels = {
            "request_title": "Give your idea a short name",
            "item_type": "What sort of item are you thinking about?",
            "description": "Tell us your idea",
            "inspiration_source": "What inspired your idea?",
        }

        widgets = {
            "request_title": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Alfie's Football Memory Box"
                }
            ),

            "item_type": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Sign, memorial, gift box, frame, "
                        "decoration or something completely unique"
                    )
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": (
                        "Tell us what you would like made. "
                        "Your idea doesn't need to be fully worked out. "
                        "Even a rough idea is a great place to start..."
                    ),
                }
            ),

            "inspiration_source": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. A memory, hobby, pet, place, "
                        "photograph or something you've seen"
                    )
                }
            ),
        }


# =========================================================
# STEP 2
# RECIPIENT & OCCASION
# =========================================================

class BespokeRecipientForm(BaseWizardForm):

    class Meta:
        model = BespokeRequest

        fields = [
            "recipient_name",
            "recipient_relationship",
            "recipient_age",
            "occasion",
            "occasion_date",
            "recipient_interests",
            "story_or_meaning",
        ]

        labels = {
            "recipient_name": "Who is the gift for?",
            "recipient_relationship": "Who are they to you?",
            "recipient_age": "Age or age range",
            "occasion": "What is the occasion?",
            "occasion_date": "When is the occasion?",
            "recipient_interests": (
                "What are they interested in?"
            ),
            "story_or_meaning": (
                "Is there a story or special meaning behind the gift?"
            ),
        }

        widgets = {
            "recipient_name": forms.TextInput(
                attrs={
                    "placeholder": "Name or nickname"
                }
            ),

            "recipient_relationship": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Husband, Mum, friend, colleague"
                    )
                }
            ),

            "recipient_age": forms.TextInput(
                attrs={
                    "placeholder": "e.g. 40, 10 years old, in their 60s"
                }
            ),

            "occasion": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Birthday, wedding, memorial, Christmas"
                    )
                }
            ),

            "occasion_date": DateInput(),

            "recipient_interests": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Hobbies, favourite colours, animals, sports, "
                        "music, places, interests, personality..."
                    )
                }
            ),

            "story_or_meaning": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Tell us anything that could make the finished "
                        "gift more personal or meaningful..."
                    )
                }
            ),
        }


# =========================================================
# STEP 3
# DESIGN & PERSONALISATION
# =========================================================

class BespokeDesignForm(BaseWizardForm):

    class Meta:
        model = BespokeRequest

        fields = [
            "style",
            "theme",
            "colours",
            "materials",
            "size_or_dimensions",
            "personalisation_text",
            "must_include",
            "avoid",
            "finish_notes",
        ]

        labels = {
            "style": "What style or feel would you like?",
            "theme": "Theme",
            "colours": "Colours",
            "materials": "Preferred materials",
            "size_or_dimensions": "Size or dimensions",
            "personalisation_text": (
                "Names, dates, wording or personalisation"
            ),
            "must_include": "What absolutely must be included?",
            "avoid": "Anything you definitely don't want?",
            "finish_notes": (
                "Any ideas for the finish, display or packaging?"
            ),
        }

        widgets = {
            "style": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Rustic, modern, funny, elegant, colourful"
                    )
                }
            ),

            "theme": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Westies, fishing, football, flowers"
                    )
                }
            ),

            "colours": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Blue and silver, natural wood, pastel colours"
                    )
                }
            ),

            "materials": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Wood, acrylic, vinyl, fabric, no preference"
                    )
                }
            ),

            "size_or_dimensions": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Approx 30cm wide, A4 size, not sure"
                    )
                }
            ),

            "personalisation_text": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Names, dates, messages, quotes or exact wording..."
                    )
                }
            ),

            "must_include": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Tell us anything that absolutely has to be "
                        "part of the finished item..."
                    )
                }
            ),

            "avoid": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Colours, styles, wording or ideas you'd rather avoid..."
                    )
                }
            ),

            "finish_notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Glossy, matt, rustic, wall mounted, gift boxed, "
                        "freestanding..."
                    )
                }
            ),
        }


# =========================================================
# STEP 4
# BUDGET, DEADLINE & PRACTICAL DETAILS
# =========================================================

class BespokePracticalForm(BaseWizardForm):

    class Meta:
        model = BespokeRequest

        fields = [
            "quantity",
            "budget_min",
            "budget_max",
            "budget_flexible",
            "needed_by",
            "deadline_flexible",
            "fulfilment",
            "delivery_postcode",
            "practical_notes",
        ]

        labels = {
            "quantity": "How many do you need?",
            "budget_min": "Budget from",
            "budget_max": "Budget up to",
            "budget_flexible": "My budget is flexible",
            "needed_by": "When would you ideally like it?",
            "deadline_flexible": "The date is flexible",
            "fulfilment": "How would you like to receive it?",
            "delivery_postcode": "Delivery postcode",
            "practical_notes": (
                "Anything else we should know?"
            ),
        }

        widgets = {
            "quantity": forms.NumberInput(
                attrs={
                    "min": "1",
                }
            ),

            "budget_min": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "£"
                }
            ),

            "budget_max": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "£"
                }
            ),

            "needed_by": DateInput(),

            "delivery_postcode": forms.TextInput(
                attrs={
                    "placeholder": "e.g. SG18 0AA"
                }
            ),

            "practical_notes": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Packaging requirements, delivery information, "
                        "special considerations or anything else..."
                    )
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        budget_min = cleaned_data.get("budget_min")
        budget_max = cleaned_data.get("budget_max")

        if (
            budget_min is not None
            and budget_max is not None
            and budget_min > budget_max
        ):
            self.add_error(
                "budget_max",
                "The maximum budget cannot be lower than the minimum budget.",
            )

        return cleaned_data


# =========================================================
# STEP 5
# CUSTOMER CONTACT DETAILS
# =========================================================

class BespokeContactForm(BaseWizardForm):

    class Meta:
        model = BespokeRequest

        fields = [
            "name",
            "email",
            "phone",
            "preferred_contact",
            "best_contact_time",
        ]

        labels = {
            "name": "Your full name",
            "email": "Email address",
            "phone": "Phone number",
            "preferred_contact": (
                "How would you prefer us to contact you?"
            ),
            "best_contact_time": (
                "Is there a good time to contact you?"
            ),
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Your full name"
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "placeholder": "you@example.com"
                }
            ),

            "phone": forms.TextInput(
                attrs={
                    "placeholder": "Optional unless phone contact is preferred"
                }
            ),

            "best_contact_time": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Evenings, weekends, anytime"
                    )
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data.get("email")
        phone = cleaned_data.get("phone")
        preferred_contact = cleaned_data.get(
            "preferred_contact"
        )

        if not email:
            self.add_error(
                "email",
                "Please enter an email address so we can reply to you.",
            )

        if (
            preferred_contact
            == BespokeRequest.PreferredContact.PHONE
            and not phone
        ):
            self.add_error(
                "phone",
                (
                    "Please enter a phone number if you would "
                    "prefer us to contact you by phone."
                ),
            )

        return cleaned_data


# =========================================================
# STEP 6
# REVIEW & SUBMIT
# =========================================================

class BespokeSubmitForm(BaseWizardForm):

    class Meta:
        model = BespokeRequest

        fields = [
            "details_confirmed",
            "terms_accepted",
            "contact_consent",
        ]

        labels = {
            "details_confirmed": (
                "I have reviewed my bespoke request and the details "
                "are correct."
            ),

            "terms_accepted": (
                "I understand that this is a bespoke enquiry and "
                "not yet a confirmed order or final price."
            ),

            "contact_consent": (
                "I am happy for K9 to contact me about this "
                "bespoke request."
            ),
        }

    def clean_details_confirmed(self):
        value = self.cleaned_data.get(
            "details_confirmed"
        )

        if not value:
            raise forms.ValidationError(
                "Please confirm that you have reviewed your request."
            )

        return value

    def clean_terms_accepted(self):
        value = self.cleaned_data.get(
            "terms_accepted"
        )

        if not value:
            raise forms.ValidationError(
                "Please confirm that you understand this is an enquiry."
            )

        return value

    def clean_contact_consent(self):
        value = self.cleaned_data.get(
            "contact_consent"
        )

        if not value:
            raise forms.ValidationError(
                "We need permission to contact you about your request."
            )

        return value
