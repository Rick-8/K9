from decimal import Decimal
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from .models import (
    BespokeDesign,
    BespokeDesignVersion,
    BespokeOrderWorkflow,
    BespokeQuote,
    BespokeQuoteLine,
    OrderCommunication,
)


User = get_user_model()


# =========================================================
# SHARED FILE VALIDATION
# =========================================================

def validate_temporary_attachment(
    attachment,
    allowed_extensions,
    max_size_mb=15,
):
    """
    Validate an uploaded file that will be used temporarily.

    The file is not permanently stored by K9.
    """

    if not attachment:
        return attachment

    max_size = (
        max_size_mb
        * 1024
        * 1024
    )

    if attachment.size > max_size:
        raise forms.ValidationError(
            (
                "The file is too large. "
                f"The maximum file size is "
                f"{max_size_mb} MB."
            )
        )

    extension = (
        Path(attachment.name)
        .suffix
        .lower()
    )

    if extension not in allowed_extensions:
        raise forms.ValidationError(
            "This file type is not currently supported."
        )

    return attachment


# =========================================================
# BESPOKE JOB ASSIGNMENT
# =========================================================

class BespokeJobAssignmentForm(forms.ModelForm):
    """
    Allows a superuser to assign or reassign a bespoke
    job to an active staff member.
    """

    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="Unassigned",
        label="Assign to",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    class Meta:
        model = BespokeOrderWorkflow

        fields = [
            "assigned_to",
        ]

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields[
            "assigned_to"
        ].queryset = (
            User.objects
            .filter(
                is_active=True,
                is_staff=True,
            )
            .order_by(
                "first_name",
                "last_name",
                "username",
            )
        )


# =========================================================
# GENERIC BESPOKE WORKFLOW FORM
# =========================================================

class BespokeJobWorkflowForm(forms.ModelForm):
    """
    Shared workflow controls used throughout the bespoke
    job wizard.
    """

    class Meta:
        model = BespokeOrderWorkflow

        fields = [
            "priority",
            "staff_summary",
            "next_action",
            "next_action_due",
            "customer_waiting",
        ]

        widgets = {

            "priority": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "staff_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Record the important current "
                        "details of this job..."
                    ),
                }
            ),

            "next_action": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "What needs to happen next?"
                    ),
                }
            ),

            "next_action_due": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
            ),

            "customer_waiting": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

        labels = {
            "priority": "Job Priority",
            "staff_summary": "Working Summary",
            "next_action": "Next Action",
            "next_action_due": "Next Action Due",
            "customer_waiting": "Waiting for Customer",
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields[
            "next_action_due"
        ].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]


# =========================================================
# STEP 2 - CUSTOMER EMAIL
# =========================================================

class CustomerEmailForm(forms.Form):
    """
    Standard customer email form.

    Attachments are sent directly from request.FILES and are
    not permanently stored by K9.
    """

    subject = forms.CharField(
        max_length=255,
        label="Email Subject",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Enter the email subject..."
                ),
                "autocomplete": "off",
            }
        ),
    )

    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 9,
                "placeholder": (
                    "Write your message to the customer..."
                ),
            }
        ),
    )

    attachment = forms.FileField(
        required=False,
        label="Attach Photo or Document",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": (
                    ".jpg,.jpeg,.png,.webp,.heic,"
                    ".pdf,.doc,.docx,.txt"
                ),
            }
        ),
        help_text=(
            "Optional. JPG, PNG, WEBP, HEIC, PDF, "
            "Word or text files. Maximum 15 MB."
        ),
    )

    def clean_attachment(self):

        attachment = (
            self.cleaned_data.get(
                "attachment"
            )
        )

        return validate_temporary_attachment(
            attachment,
            {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".heic",
                ".pdf",
                ".doc",
                ".docx",
                ".txt",
            },
            max_size_mb=15,
        )


# =========================================================
# STEP 2 - WHATSAPP
# =========================================================

class WhatsAppMessageForm(forms.Form):
    """
    Builds a prepared WhatsApp message.
    """

    message = forms.CharField(
        label="WhatsApp Message",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": (
                    "Write the WhatsApp message..."
                ),
            }
        ),
    )


# =========================================================
# STEP 2 - MANUAL COMMUNICATION LOG
# =========================================================

class CommunicationLogForm(forms.Form):
    """
    Used for communication that cannot be captured
    automatically.
    """

    CONTACT_CHANNEL_CHOICES = [
        (
            OrderCommunication.Channel.PHONE,
            "Phone Call",
        ),
        (
            OrderCommunication.Channel.WHATSAPP,
            "WhatsApp",
        ),
        (
            OrderCommunication.Channel.IN_PERSON,
            "In Person",
        ),
        (
            OrderCommunication.Channel.OTHER,
            "Other",
        ),
    ]

    channel = forms.ChoiceField(
        label="Contact Method",
        choices=CONTACT_CHANNEL_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    direction = forms.ChoiceField(
        label="Direction",
        choices=(
            OrderCommunication
            .Direction
            .choices
        ),
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    summary = forms.CharField(
        max_length=255,
        label="Summary",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "e.g. Discussed colour choices"
                ),
                "autocomplete": "off",
            }
        ),
    )

    content = forms.CharField(
        required=False,
        label="Details / Notes",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": (
                    "Record the important details "
                    "of the conversation..."
                ),
            }
        ),
    )

    occurred_at = forms.DateTimeField(
        required=False,
        label="Date & Time",
        input_formats=[
            "%Y-%m-%dT%H:%M",
        ],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            }
        ),
        help_text=(
            "Leave blank to use the current date and time."
        ),
    )


# =========================================================
# STEP 3 - MASTER DESIGN BRIEF
# =========================================================

class BespokeDesignMasterForm(forms.ModelForm):
    """
    Master design/specification record.

    This describes the overall job rather than one specific
    customer-facing revision.
    """

    class Meta:
        model = BespokeDesign

        fields = [
            "specification",
            "internal_notes",
        ]

        widgets = {

            "specification": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": (
                        "Record the overall design brief, "
                        "dimensions, colours, materials, wording, "
                        "personalisation and customer requirements..."
                    ),
                }
            ),

            "internal_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Private staff notes about the overall "
                        "design brief..."
                    ),
                }
            ),
        }

        labels = {
            "specification": (
                "Master Design Specification"
            ),
            "internal_notes": (
                "Internal Design Notes"
            ),
        }

        help_texts = {
            "specification": (
                "This is the master brief shared by all "
                "design versions."
            ),
            "internal_notes": (
                "Staff-only information. Customers never "
                "see these notes."
            ),
        }


# =========================================================
# STEP 3 - LEGACY DESIGN FORM
#
# Kept temporarily while the Step 3 view/template is being
# migrated to the new versioned design system.
# =========================================================

class BespokeDesignForm(forms.ModelForm):

    class Meta:
        model = BespokeDesign

        fields = [
            "specification",
            "internal_notes",
            "final_design_summary",
            "final_design_ready",
        ]

        widgets = {

            "specification": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                }
            ),

            "internal_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                }
            ),

            "final_design_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                }
            ),

            "final_design_ready": (
                forms.CheckboxInput(
                    attrs={
                        "class": "form-check-input",
                    }
                )
            ),
        }


# =========================================================
# STEP 3 - DESIGN VERSION
# =========================================================

class BespokeDesignVersionForm(forms.ModelForm):
    """
    Create or edit one design revision.

    Status and version number are managed by K9 and therefore
    are deliberately not editable here.
    """

    class Meta:
        model = BespokeDesignVersion

        fields = [
            "title",
            "customer_summary",
            "change_summary",
            "staff_notes",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Optional name, e.g. "
                        "Oak plaque with larger Westie"
                    ),
                    "autocomplete": "off",
                }
            ),

            "customer_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Describe this design clearly for the "
                        "customer. This wording will appear on "
                        "their design review page."
                    ),
                }
            ),

            "change_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "What changed from the previous version?"
                    ),
                }
            ),

            "staff_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Private notes about this version..."
                    ),
                }
            ),
        }

        labels = {
            "title": "Design Version Title",
            "customer_summary": (
                "Customer Design Description"
            ),
            "change_summary": (
                "Changes From Previous Version"
            ),
            "staff_notes": (
                "Internal Staff Notes"
            ),
        }

        help_texts = {
            "title": (
                "Optional. Helps staff identify this revision."
            ),
            "customer_summary": (
                "Customer-facing. Explain exactly what this "
                "version represents."
            ),
            "change_summary": (
                "Useful for V2, V3 and later revisions."
            ),
            "staff_notes": (
                "Staff-only. Never displayed to the customer."
            ),
        }


# =========================================================
# STEP 3 - EMAIL A SPECIFIC DESIGN VERSION
# =========================================================

class DesignVersionEmailForm(forms.Form):
    """
    Email one exact design version to the customer.

    The selected local file is sent as an attachment and is
    not permanently stored. Its metadata/fingerprint is saved
    against BespokeDesignVersion by the view.
    """

    subject = forms.CharField(
        max_length=255,
        label="Email Subject",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "placeholder": (
                    "Your K9 bespoke design is ready to review"
                ),
            }
        ),
    )

    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": (
                    "Explain this design version and ask the "
                    "customer to review it..."
                ),
            }
        ),
    )

    attachment = forms.FileField(
        required=False,
        label="Attach Design File",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": (
                    ".jpg,.jpeg,.png,.webp,.heic,"
                    ".pdf,.doc,.docx,.txt,"
                    ".mp4,.mov,.m4v"
                ),
            }
        ),
        help_text=(
            "Optional. Photo, PDF, document or short video. "
            "Maximum 15 MB. The file is emailed but not "
            "permanently stored."
        ),
    )

    def clean_attachment(self):

        attachment = (
            self.cleaned_data.get(
                "attachment"
            )
        )

        return validate_temporary_attachment(
            attachment,
            {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".heic",
                ".pdf",
                ".doc",
                ".docx",
                ".txt",
                ".mp4",
                ".mov",
                ".m4v",
            },
            max_size_mb=15,
        )


# =========================================================
# STEP 3 - EXISTING DESIGN EMAIL
#
# Retained temporarily until the Step 3 view has completely
# moved to DesignVersionEmailForm.
# =========================================================

class DesignCustomerEmailForm(forms.Form):

    subject = forms.CharField(
        max_length=255,
        label="Email Subject",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
            }
        ),
    )

    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
            }
        ),
    )

    attachment = forms.FileField(
        required=False,
        label="Attach Design File",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": (
                    ".jpg,.jpeg,.png,.webp,.heic,"
                    ".pdf,.doc,.docx,.txt,"
                    ".mp4,.mov,.m4v"
                ),
            }
        ),
        help_text=(
            "Optional. Maximum 15 MB."
        ),
    )

    def clean_attachment(self):

        attachment = (
            self.cleaned_data.get(
                "attachment"
            )
        )

        return validate_temporary_attachment(
            attachment,
            {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".heic",
                ".pdf",
                ".doc",
                ".docx",
                ".txt",
                ".mp4",
                ".mov",
                ".m4v",
            },
            max_size_mb=15,
        )


# =========================================================
# PUBLIC CUSTOMER DESIGN RESPONSE
# =========================================================

class CustomerDesignResponseForm(forms.Form):
    """
    Used on the secure customer design review page.

    The view passes decision="accept" or decision="reject".

    A rejection / change request requires comments.
    """

    response_name = forms.CharField(
        max_length=200,
        label="Your Name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "name",
            }
        ),
    )

    response_email = forms.EmailField(
        label="Your Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
            }
        ),
    )

    response_notes = forms.CharField(
        required=False,
        label="Comments",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": (
                    "Add any comments or describe the "
                    "changes you would like..."
                ),
            }
        ),
    )

    def __init__(
        self,
        *args,
        decision=None,
        **kwargs,
    ):
        self.decision = decision

        super().__init__(
            *args,
            **kwargs,
        )

    def clean(self):

        cleaned_data = super().clean()

        notes = (
            cleaned_data.get(
                "response_notes",
                ""
            )
            .strip()
        )

        if (
            self.decision == "reject"
            and not notes
        ):
            self.add_error(
                "response_notes",
                (
                    "Please tell us what you would like "
                    "changed before submitting your request."
                ),
            )

        return cleaned_data


# =========================================================
# STEP 4 - QUOTE DETAILS
# =========================================================

class BespokeQuoteForm(forms.ModelForm):
    """
    Main quotation information.

    All pricing and VAT decisions are entered by staff.
    K9 only performs the calculations.

    Quote version numbers and calculated totals are managed
    by the system.
    """

    class Meta:
        model = BespokeQuote

        fields = [
            "title",
            "notes",
            "delivery_cost",
            "vat_enabled",
            "vat_rate",
            "vat_on_delivery",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. Custom Westie Memorial Plaque"
                    ),
                    "autocomplete": "off",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Optional information to show with "
                        "the quotation, such as timescale, "
                        "materials or important conditions..."
                    ),
                }
            ),

            "delivery_cost": forms.NumberInput(
                attrs={
                    "class": "form-control quote-delivery-cost",
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),

            "vat_enabled": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input quote-vat-enabled",
                }
            ),

            "vat_rate": forms.NumberInput(
                attrs={
                    "class": "form-control quote-vat-rate",
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                    "placeholder": "20.00",
                }
            ),

            "vat_on_delivery": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input quote-vat-on-delivery",
                }
            ),
        }

        labels = {
            "title": "Quote Title",
            "notes": "Customer Quote Notes",
            "delivery_cost": "Delivery / Postage (£)",
            "vat_enabled": "Apply VAT",
            "vat_rate": "VAT Rate (%)",
            "vat_on_delivery": "Apply VAT to Delivery",
        }

        help_texts = {
            "notes": (
                "These notes are customer-facing and will "
                "appear in the quote preview."
            ),
            "delivery_cost": (
                "Enter the delivery charge manually. "
                "Use 0.00 if delivery is included or free."
            ),
            "vat_enabled": (
                "Staff controls whether VAT applies to "
                "this quote."
            ),
            "vat_rate": (
                "Enter the VAT percentage to use for "
                "this quote."
            ),
            "vat_on_delivery": (
                "Include the delivery charge when "
                "calculating VAT."
            ),
        }

    def clean_delivery_cost(self):

        value = (
            self.cleaned_data.get(
                "delivery_cost"
            )
        )

        if value is None:
            return Decimal("0.00")

        if value < 0:
            raise forms.ValidationError(
                "Delivery cost cannot be negative."
            )

        return value

    def clean_vat_rate(self):

        value = (
            self.cleaned_data.get(
                "vat_rate"
            )
        )

        if value is None:
            return Decimal("0.00")

        if value < 0:
            raise forms.ValidationError(
                "VAT rate cannot be negative."
            )

        if value > 100:
            raise forms.ValidationError(
                "VAT rate cannot be more than 100%."
            )

        return value

    def clean(self):

        cleaned_data = super().clean()

        vat_enabled = cleaned_data.get(
            "vat_enabled"
        )

        vat_rate = cleaned_data.get(
            "vat_rate"
        )

        if (
            vat_enabled
            and (
                vat_rate is None
                or vat_rate <= 0
            )
        ):
            self.add_error(
                "vat_rate",
                (
                    "Enter a VAT rate greater than 0 "
                    "when VAT is enabled."
                ),
            )

        return cleaned_data

    def save(
        self,
        commit=True,
    ):
        """
        Save staff-entered quote settings.

        If saved immediately, refresh the calculated totals
        using the model's VAT-aware calculation method.
        """

        quote = super().save(
            commit=commit
        )

        if (
            commit
            and quote.pk
        ):
            quote.recalculate_totals()
            quote.refresh_from_db()

        return quote


# =========================================================
# STEP 4 - QUOTE LINE
# =========================================================

class BespokeQuoteLineForm(forms.ModelForm):
    """
    One staff-entered quotation line.

    K9 never creates or suggests pricing here.
    """

    class Meta:
        model = BespokeQuoteLine

        fields = [
            "description",
            "quantity",
            "unit_price",
            "sort_order",
        ]

        widgets = {

            "description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. Handmade personalised plaque"
                    ),
                    "autocomplete": "off",
                }
            ),

            "quantity": forms.NumberInput(
                attrs={
                    "class": (
                        "form-control quote-quantity"
                    ),
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "unit_price": forms.NumberInput(
                attrs={
                    "class": (
                        "form-control quote-unit-price"
                    ),
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),

            "sort_order": forms.HiddenInput(),
        }

        labels = {
            "description": "Description",
            "quantity": "Qty",
            "unit_price": "Unit Price (£)",
        }

        help_texts = {
            "unit_price": (
                "Price entered manually by staff."
            ),
        }

    def clean_quantity(self):

        quantity = (
            self.cleaned_data.get(
                "quantity"
            )
        )

        if (
            quantity is not None
            and quantity <= 0
        ):
            raise forms.ValidationError(
                "Quantity must be greater than zero."
            )

        return quantity

    def clean_unit_price(self):

        unit_price = (
            self.cleaned_data.get(
                "unit_price"
            )
        )

        if unit_price is None:
            return Decimal("0.00")

        if unit_price < 0:
            raise forms.ValidationError(
                "Unit price cannot be negative."
            )

        return unit_price


# =========================================================
# STEP 4 - QUOTE LINE FORMSET
# =========================================================

BespokeQuoteLineFormSet = inlineformset_factory(
    BespokeQuote,
    BespokeQuoteLine,
    form=BespokeQuoteLineForm,
    fields=[
        "description",
        "quantity",
        "unit_price",
        "sort_order",
    ],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
