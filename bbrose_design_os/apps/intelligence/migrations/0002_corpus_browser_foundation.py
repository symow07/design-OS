import apps.intelligence.models
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0001_source_foundation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SourceLocationObservation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('observed_location', models.CharField(max_length=1024)),
                ('location_kind', models.CharField(choices=[('REPOSITORY_RELATIVE', 'Repository Relative'), ('CONFIGURED_ROOT_RELATIVE', 'Configured Root Relative'), ('ARCHIVE_MEMBER', 'Archive Member'), ('LOGICAL', 'Logical')], max_length=32)),
                ('observed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('availability_state', models.CharField(choices=[('AVAILABLE', 'Available'), ('MISSING', 'Missing'), ('ARCHIVED', 'Archived'), ('UNKNOWN', 'Unknown')], default='UNKNOWN', max_length=16)),
                ('location_metadata', models.JSONField(blank=True, default=dict, validators=[apps.intelligence.models._validate_locator])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('observed_by_import_record', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='source_location_observations', to='intelligence.importrecord')),
                ('source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='location_observations', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='ObservedFact',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('fact_type', models.CharField(max_length=64)),
                ('normalized_value', models.JSONField(validators=[apps.intelligence.models._validate_locator])),
                ('raw_value', models.TextField(blank=True)),
                ('value_schema_version', models.CharField(max_length=64)),
                ('importer_identifier', models.CharField(max_length=127)),
                ('importer_version', models.CharField(max_length=64)),
                ('fact_hash', models.CharField(max_length=64)),
                ('observed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('corpus_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='observed_facts', to='intelligence.corpusitem')),
                ('evidence_reference', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='observed_facts', to='intelligence.evidencereference')),
                ('source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='observed_facts', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='MachineClassification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('classification_type', models.CharField(max_length=64)),
                ('label', models.CharField(max_length=255)),
                ('confidence', models.DecimalField(decimal_places=4, max_digits=5)),
                ('classifier_identifier', models.CharField(max_length=127)),
                ('classifier_version', models.CharField(max_length=64)),
                ('classification_schema_version', models.CharField(max_length=64)),
                ('structured_explanation', models.JSONField(blank=True, default=dict, validators=[apps.intelligence.models._validate_locator])),
                ('classification_hash', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('corpus_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='machine_classifications', to='intelligence.corpusitem')),
                ('evidence_reference', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='machine_classifications', to='intelligence.evidencereference')),
                ('source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='machine_classifications', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalDesignProfile',
            fields=[
                ('corpus_item', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name='historical_design_profile', serialize=False, to='intelligence.corpusitem')),
                ('display_title', models.CharField(max_length=255)),
                ('page_artboard_count', models.PositiveIntegerField(default=0)),
                ('extracted_design_unit_count', models.PositiveIntegerField(default=0)),
                ('audit_status', models.CharField(choices=[('MACHINE_AUDITED', 'Machine Audited'), ('PARTIAL', 'Partial'), ('REVIEW_REQUIRED', 'Review Required')], max_length=24)),
                ('historical_period_observed', models.CharField(blank=True, max_length=127)),
                ('product_family_machine_label', models.CharField(blank=True, max_length=127)),
                ('reference_memory_policy', models.CharField(default='REFERENCE_MEMORY_ONLY', editable=False, max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('primary_source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='historical_design_profiles', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='FontFaceProfile',
            fields=[
                ('corpus_item', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name='font_face_profile', serialize=False, to='intelligence.corpusitem')),
                ('face_index', models.PositiveIntegerField(default=0)),
                ('family_name', models.CharField(max_length=255)),
                ('subfamily', models.CharField(blank=True, max_length=255)),
                ('postscript_name', models.CharField(blank=True, max_length=255)),
                ('weight', models.PositiveIntegerField(blank=True, null=True)),
                ('width', models.CharField(blank=True, max_length=32)),
                ('italic', models.BooleanField(default=False)),
                ('variable_axes', models.JSONField(blank=True, default=list, validators=[apps.intelligence.models._validate_bounded_json])),
                ('script_coverage', models.JSONField(blank=True, default=dict, validators=[apps.intelligence.models._validate_locator])),
                ('suspected_system_copy', models.BooleanField(default=False)),
                ('evidence_state', models.CharField(choices=[('UNREVIEWED', 'Unreviewed'), ('PRESENT_UNREVIEWED', 'Present Unreviewed'), ('ABSENT', 'Absent'), ('CONFLICT', 'Conflict')], max_length=24)),
                ('technical_suitability_state', models.CharField(choices=[('HEALTHY', 'Healthy'), ('TECHNICAL_CAVEAT', 'Technical Caveat'), ('UNSUPPORTED', 'Unsupported'), ('REVIEW_REQUIRED', 'Review Required')], max_length=24)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('primary_source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='font_face_profiles', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='DesignUnit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('stable_unit_key', models.CharField(max_length=255)),
                ('unit_type', models.CharField(choices=[('SURFACE_ARTWORK', 'Surface Artwork'), ('TECHNICAL_NOTES', 'Technical Notes'), ('PRODUCT_PHOTO', 'Product Photo'), ('DIELINE_CANDIDATE', 'Dieline Candidate'), ('SPEC_TABLE', 'Spec Table'), ('LEGAL_TEXT', 'Legal Text'), ('UNKNOWN', 'Unknown'), ('COLOR_PALETTE_STRIP', 'Color Palette Strip'), ('BARCODE', 'Barcode')], max_length=32)),
                ('ordinal', models.PositiveIntegerField()),
                ('source_page_artboard', models.PositiveIntegerField(blank=True, null=True)),
                ('geometry_x', models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True)),
                ('geometry_y', models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True)),
                ('geometry_width', models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True)),
                ('geometry_height', models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True)),
                ('technical_summary', models.TextField(blank=True)),
                ('extraction_status', models.CharField(choices=[('AUTO_CONFIDENT', 'Auto Confident'), ('AUTO_LOW_CONFIDENCE', 'Auto Low Confidence'), ('REVIEW_REQUIRED', 'Review Required'), ('UNAVAILABLE', 'Unavailable')], max_length=24)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('evidence_reference', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='design_units', to='intelligence.evidencereference')),
                ('historical_design_profile', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='design_units', to='intelligence.historicaldesignprofile')),
                ('source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='design_units', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='DesignAssetProfile',
            fields=[
                ('corpus_item', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name='design_asset_profile', serialize=False, to='intelligence.corpusitem')),
                ('candidate_source_key', models.CharField(max_length=64)),
                ('source_manifest_entry_key', models.CharField(max_length=255)),
                ('dataset_identifier', models.CharField(max_length=127)),
                ('candidate_asset_kind', models.CharField(choices=[('MOTIF', 'Motif'), ('BACKGROUND', 'Background'), ('ILLUSTRATION', 'Illustration'), ('LOGO_CANDIDATE', 'Logo Candidate'), ('PATTERN', 'Pattern'), ('PHOTO', 'Photo'), ('UNKNOWN', 'Unknown')], max_length=24)),
                ('representation_state', models.CharField(choices=[('VECTOR', 'Vector'), ('RASTER', 'Raster'), ('MIXED', 'Mixed'), ('UNKNOWN', 'Unknown')], max_length=16)),
                ('technical_readiness', models.CharField(choices=[('TECHNICALLY_READY', 'Technically Ready'), ('TECHNICALLY_USABLE_WITH_CAVEATS', 'Technically Usable With Caveats'), ('NEEDS_VECTOR_RECONSTRUCTION', 'Needs Vector Reconstruction'), ('REFERENCE_ONLY', 'Reference Only'), ('NEEDS_CLEANUP', 'Needs Cleanup'), ('HEADER_ONLY_PARTIAL', 'Header Only Partial'), ('REVIEW_REQUIRED', 'Review Required')], max_length=40)),
                ('extraction_state', models.CharField(max_length=32)),
                ('collection_family_label', models.CharField(blank=True, max_length=255)),
                ('dimensions_media', models.JSONField(blank=True, default=dict, validators=[apps.intelligence.models._validate_locator])),
                ('is_test_only', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('primary_source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='design_asset_profiles', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.CreateModel(
            name='BrandCandidateProfile',
            fields=[
                ('corpus_item', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name='brand_candidate_profile', serialize=False, to='intelligence.corpusitem')),
                ('candidate_kind', models.CharField(choices=[('LOGO', 'Logo'), ('WORDMARK', 'Wordmark'), ('BRAND_GRAPHIC', 'Brand Graphic'), ('PALETTE', 'Palette'), ('LOCKUP', 'Lockup'), ('UNKNOWN_BRAND_ASSET', 'Unknown Brand Asset')], max_length=24)),
                ('observed_brand_label', models.CharField(blank=True, max_length=255)),
                ('technical_format', models.CharField(max_length=32)),
                ('representation_state', models.CharField(choices=[('VECTOR', 'Vector'), ('RASTER', 'Raster'), ('MIXED', 'Mixed'), ('UNKNOWN', 'Unknown')], max_length=16)),
                ('observed_candidate_data', models.JSONField(blank=True, default=dict, validators=[apps.intelligence.models._validate_locator])),
                ('warning_state', models.CharField(choices=[('NONE_OBSERVED', 'None Observed'), ('REQUIRES_REVIEW', 'Requires Review'), ('THIRD_PARTY_OR_UNCONFIRMED', 'Third Party Or Unconfirmed'), ('PARTIAL_PARSE', 'Partial Parse')], max_length=32)),
                ('candidate_status', models.CharField(choices=[('CANDIDATE', 'Candidate'), ('UNCONFIRMED', 'Unconfirmed'), ('REVIEW_REQUIRED', 'Review Required')], max_length=24)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('primary_source_artifact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='brand_candidate_profiles', to='intelligence.sourceartifact')),
            ],
        ),
        migrations.AddIndex(
            model_name='sourcelocationobservation',
            index=models.Index(fields=['source_artifact', 'observed_at'], name='intel_location_history_idx'),
        ),
        migrations.AddConstraint(
            model_name='sourcelocationobservation',
            constraint=models.CheckConstraint(check=models.Q(('location_kind__in', ('REPOSITORY_RELATIVE', 'CONFIGURED_ROOT_RELATIVE', 'ARCHIVE_MEMBER', 'LOGICAL'))), name='intel_location_kind_valid'),
        ),
        migrations.AddConstraint(
            model_name='sourcelocationobservation',
            constraint=models.CheckConstraint(check=models.Q(('availability_state__in', ('AVAILABLE', 'MISSING', 'ARCHIVED', 'UNKNOWN'))), name='intel_location_avail_valid'),
        ),
        migrations.AddConstraint(
            model_name='sourcelocationobservation',
            constraint=models.UniqueConstraint(fields=('source_artifact', 'location_kind', 'observed_location'), name='intel_location_artifact_path_uniq'),
        ),
        migrations.AddIndex(
            model_name='observedfact',
            index=models.Index(fields=['corpus_item', 'fact_type', 'created_at'], name='intel_fact_item_type_idx'),
        ),
        migrations.AddConstraint(
            model_name='observedfact',
            constraint=models.CheckConstraint(check=models.Q(('fact_hash__regex', '^[0-9a-f]{64}$')), name='intel_fact_hash_valid'),
        ),
        migrations.AddConstraint(
            model_name='observedfact',
            constraint=models.UniqueConstraint(fields=('corpus_item', 'fact_type', 'source_artifact', 'fact_hash'), name='intel_fact_item_type_src_hash_uniq'),
        ),
        migrations.AddIndex(
            model_name='machineclassification',
            index=models.Index(fields=['corpus_item', 'classification_type', 'created_at'], name='intel_class_item_type_idx'),
        ),
        migrations.AddConstraint(
            model_name='machineclassification',
            constraint=models.CheckConstraint(check=models.Q(('confidence__gte', 0), ('confidence__lte', 1)), name='intel_class_confidence_range'),
        ),
        migrations.AddConstraint(
            model_name='machineclassification',
            constraint=models.CheckConstraint(check=models.Q(('classification_hash__regex', '^[0-9a-f]{64}$')), name='intel_class_hash_valid'),
        ),
        migrations.AddConstraint(
            model_name='machineclassification',
            constraint=models.UniqueConstraint(fields=('corpus_item', 'classification_type', 'source_artifact', 'classification_hash'), name='intel_class_item_type_src_hash_uniq'),
        ),
        migrations.AddConstraint(
            model_name='historicaldesignprofile',
            constraint=models.CheckConstraint(check=models.Q(('page_artboard_count__lte', 100000)), name='intel_hist_page_count_bounded'),
        ),
        migrations.AddConstraint(
            model_name='historicaldesignprofile',
            constraint=models.CheckConstraint(check=models.Q(('extracted_design_unit_count__lte', 1000000)), name='intel_hist_unit_count_bounded'),
        ),
        migrations.AddConstraint(
            model_name='historicaldesignprofile',
            constraint=models.CheckConstraint(check=models.Q(('audit_status__in', ('MACHINE_AUDITED', 'PARTIAL', 'REVIEW_REQUIRED'))), name='intel_hist_audit_status_valid'),
        ),
        migrations.AddConstraint(
            model_name='historicaldesignprofile',
            constraint=models.CheckConstraint(check=models.Q(('reference_memory_policy', 'REFERENCE_MEMORY_ONLY')), name='intel_hist_reference_only'),
        ),
        migrations.AddConstraint(
            model_name='fontfaceprofile',
            constraint=models.CheckConstraint(check=models.Q(('face_index__lte', 65535)), name='intel_font_face_index_bounded'),
        ),
        migrations.AddConstraint(
            model_name='fontfaceprofile',
            constraint=models.CheckConstraint(check=models.Q(('weight__isnull', True), models.Q(('weight__gte', 1), ('weight__lte', 1000)), _connector='OR'), name='intel_font_weight_bounded'),
        ),
        migrations.AddConstraint(
            model_name='fontfaceprofile',
            constraint=models.CheckConstraint(check=models.Q(('evidence_state__in', ('UNREVIEWED', 'PRESENT_UNREVIEWED', 'ABSENT', 'CONFLICT'))), name='intel_font_evidence_valid'),
        ),
        migrations.AddConstraint(
            model_name='fontfaceprofile',
            constraint=models.CheckConstraint(check=models.Q(('technical_suitability_state__in', ('HEALTHY', 'TECHNICAL_CAVEAT', 'UNSUPPORTED', 'REVIEW_REQUIRED'))), name='intel_font_suitability_valid'),
        ),
        migrations.AddConstraint(
            model_name='fontfaceprofile',
            constraint=models.UniqueConstraint(fields=('primary_source_artifact', 'face_index'), name='intel_font_source_face_uniq'),
        ),
        migrations.AddIndex(
            model_name='designunit',
            index=models.Index(fields=['historical_design_profile', 'ordinal'], name='intel_unit_profile_ordinal_idx'),
        ),
        migrations.AddConstraint(
            model_name='designunit',
            constraint=models.CheckConstraint(check=models.Q(('unit_type__in', ('SURFACE_ARTWORK', 'TECHNICAL_NOTES', 'PRODUCT_PHOTO', 'DIELINE_CANDIDATE', 'SPEC_TABLE', 'LEGAL_TEXT', 'UNKNOWN', 'COLOR_PALETTE_STRIP', 'BARCODE'))), name='intel_unit_type_valid'),
        ),
        migrations.AddConstraint(
            model_name='designunit',
            constraint=models.CheckConstraint(check=models.Q(('extraction_status__in', ('AUTO_CONFIDENT', 'AUTO_LOW_CONFIDENCE', 'REVIEW_REQUIRED', 'UNAVAILABLE'))), name='intel_unit_extract_valid'),
        ),
        migrations.AddConstraint(
            model_name='designunit',
            constraint=models.CheckConstraint(check=models.Q(('ordinal__lte', 1000000)), name='intel_unit_ordinal_bounded'),
        ),
        migrations.AddConstraint(
            model_name='designunit',
            constraint=models.CheckConstraint(check=models.Q(('source_page_artboard__isnull', True), ('source_page_artboard__lte', 100000), _connector='OR'), name='intel_unit_page_bounded'),
        ),
        migrations.AddConstraint(
            model_name='designunit',
            constraint=models.CheckConstraint(check=models.Q(models.Q(('geometry_x__isnull', True), ('geometry_x__gte', 0), _connector='OR'), models.Q(('geometry_y__isnull', True), ('geometry_y__gte', 0), _connector='OR'), models.Q(('geometry_width__isnull', True), ('geometry_width__gte', 0), _connector='OR'), models.Q(('geometry_height__isnull', True), ('geometry_height__gte', 0), _connector='OR')), name='intel_unit_geometry_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='designunit',
            constraint=models.UniqueConstraint(fields=('historical_design_profile', 'stable_unit_key'), name='intel_unit_profile_key_uniq'),
        ),
        migrations.AddConstraint(
            model_name='designassetprofile',
            constraint=models.CheckConstraint(check=models.Q(('dataset_identifier', 'dip0c2_asset_candidate_pilot/1.0')), name='intel_asset_c2_dataset_only'),
        ),
        migrations.AddConstraint(
            model_name='designassetprofile',
            constraint=models.CheckConstraint(check=models.Q(('candidate_asset_kind__in', ('MOTIF', 'BACKGROUND', 'ILLUSTRATION', 'LOGO_CANDIDATE', 'PATTERN', 'PHOTO', 'UNKNOWN'))), name='intel_asset_kind_valid'),
        ),
        migrations.AddConstraint(
            model_name='designassetprofile',
            constraint=models.CheckConstraint(check=models.Q(('representation_state__in', ('VECTOR', 'RASTER', 'MIXED', 'UNKNOWN'))), name='intel_asset_repr_valid'),
        ),
        migrations.AddConstraint(
            model_name='designassetprofile',
            constraint=models.CheckConstraint(check=models.Q(('technical_readiness__in', ('TECHNICALLY_READY', 'TECHNICALLY_USABLE_WITH_CAVEATS', 'NEEDS_VECTOR_RECONSTRUCTION', 'REFERENCE_ONLY', 'NEEDS_CLEANUP', 'HEADER_ONLY_PARTIAL', 'REVIEW_REQUIRED'))), name='intel_asset_readiness_valid'),
        ),
        migrations.AddConstraint(
            model_name='brandcandidateprofile',
            constraint=models.CheckConstraint(check=models.Q(('candidate_kind__in', ('LOGO', 'WORDMARK', 'BRAND_GRAPHIC', 'PALETTE', 'LOCKUP', 'UNKNOWN_BRAND_ASSET'))), name='intel_brand_kind_valid'),
        ),
        migrations.AddConstraint(
            model_name='brandcandidateprofile',
            constraint=models.CheckConstraint(check=models.Q(('representation_state__in', ('VECTOR', 'RASTER', 'MIXED', 'UNKNOWN'))), name='intel_brand_repr_valid'),
        ),
        migrations.AddConstraint(
            model_name='brandcandidateprofile',
            constraint=models.CheckConstraint(check=models.Q(('warning_state__in', ('NONE_OBSERVED', 'REQUIRES_REVIEW', 'THIRD_PARTY_OR_UNCONFIRMED', 'PARTIAL_PARSE'))), name='intel_brand_warning_valid'),
        ),
        migrations.AddConstraint(
            model_name='brandcandidateprofile',
            constraint=models.CheckConstraint(check=models.Q(('candidate_status__in', ('CANDIDATE', 'UNCONFIRMED', 'REVIEW_REQUIRED'))), name='intel_brand_status_valid'),
        ),
    ]
