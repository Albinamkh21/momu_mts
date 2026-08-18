from typing import Optional
import datetime
import decimal
import uuid

from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, String, Table, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class FindingSource(Base):
    __tablename__ = 'finding_source'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='finding_source_pkey'),
        UniqueConstraint('code', name='finding_source_code_key')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)


class Label(Base):
    __tablename__ = 'label'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='label_pkey'),
        UniqueConstraint('name', name='label_name_key'),
        Index('idx_label_name', 'name', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT, nullable=False)
    composition_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    phonogram_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    code: Mapped[Optional[str]] = mapped_column(String(30))

    release: Mapped[list['Release']] = relationship('Release', back_populates='label')
    right_holder: Mapped[list['RightHolder']] = relationship('RightHolder', back_populates='label')
    track_label: Mapped[list['TrackLabel']] = relationship('TrackLabel', back_populates='label')


t_mv_catalog_flat = Table(
    'mv_catalog_flat', Base.metadata,
    Column('track_id', BigInteger),
    Column('label_id', Integer),
    Column('upc', Text),
    Column('isrc', Text),
    Column('track_name', Text),
    Column('genre_name', Text),
    Column('album_name', Text),
    Column('track_number', Text),
    Column('artist_name', Text),
    Column('track_artist_name', Text),
    Column('composer', Text),
    Column('lyricist', Text),
    Column('authors', Text),
    Column('explicit', Text),
    Column('duration', Text),
    Column('label_name', Text),
    Column('right_id', Text),
    Column('author_right_int', Text),
    Column('author_right_mob', Text),
    Column('author_right_pub', Text),
    Column('ar_label_treaty_number', Text),
    Column('related_right_id_int', Text),
    Column('related_right_id_mob', Text),
    Column('related_right_id_pub', Text),
    Column('rr_label_treaty_number', Text),
    Index('idx_mv_catalog_flat_label_id', 'label_id'),
    Index('idx_mv_catalog_flat_track_id', 'track_id', unique=True)
)


t_mv_track_extended = Table(
    'mv_track_extended', Base.metadata,
    Column('track_id', BigInteger),
    Column('isrc', Text),
    Column('track_name', Text),
    Column('label_own_code', Text),
    Column('artist_name', Text),
    Column('track_artist_name', Text),
    Column('composer', Text),
    Column('lyricist', Text),
    Column('authors', Text),
    Column('label_id', Integer),
    Column('label_name', Text),
    Column('upc', Text),
    Column('genre_name', Text),
    Column('album_name', Text),
    Column('track_number', Text),
    Column('explicit', Text),
    Column('duration', Text),
    Column('created_at', Text),
    Index('idx__mv_track_extended__track_id', 'track_id', unique=True)
)


class Person(Base):
    __tablename__ = 'person'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='person_pkey'),
        UniqueConstraint('full_name', name='person_full_name_key'),
        Index('idx_person_full_name_norm', 'full_name'),
        Index('idx_person_norm_key', 'norm_key_full'),
        Index('idx_person_norm_key_full', 'norm_key_full'),
        Index('idx_person_tokens_gin', 'tokens', postgresql_using='gin'),
        Index('idx_person_unique_norm_key', 'norm_key_full', unique=True)
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(CITEXT, nullable=False)
    tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    norm_key_full: Mapped[Optional[str]] = mapped_column(Text)

    track_contribution: Mapped[list['TrackContribution']] = relationship('TrackContribution', back_populates='person')


class Region(Base):
    __tablename__ = 'region'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='region_pkey'),
        UniqueConstraint('code', name='region_code_key')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)

    track_right: Mapped[list['TrackRight']] = relationship('TrackRight', back_populates='region_')


class RightCategory(Base):
    __tablename__ = 'right_category'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='right_category_pkey'),
        UniqueConstraint('name', name='right_category_name_key')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    report: Mapped[list['Report']] = relationship('Report', back_populates='right_category')
    report_track_rights_cache: Mapped[list['ReportTrackRightsCache']] = relationship('ReportTrackRightsCache', back_populates='right_category')
    track_right: Mapped[list['TrackRight']] = relationship('TrackRight', back_populates='right_category')


class RightUsageType(Base):
    __tablename__ = 'right_usage_type'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='right_usage_type_pkey'),
        UniqueConstraint('code', name='right_usage_type_code_key')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)

    partners: Mapped[list['Partners']] = relationship('Partners', back_populates='right_usage_type')
    report: Mapped[list['Report']] = relationship('Report', back_populates='right_usage_type')
    report_track_rights_cache: Mapped[list['ReportTrackRightsCache']] = relationship('ReportTrackRightsCache', back_populates='right_usage_type')
    track_right: Mapped[list['TrackRight']] = relationship('TrackRight', back_populates='right_usage_type')


class StagingCatalog(Base):
    __tablename__ = 'staging_catalog'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='staging_catalog_pkey'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, server_default=text('gen_random_uuid()'))
    loaded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    upc: Mapped[Optional[str]] = mapped_column(Text)
    isrc: Mapped[Optional[str]] = mapped_column(Text)
    track_name: Mapped[Optional[str]] = mapped_column(Text)
    genre_name: Mapped[Optional[str]] = mapped_column(Text)
    album_name: Mapped[Optional[str]] = mapped_column(Text)
    album_single: Mapped[Optional[str]] = mapped_column(Text)
    track_number: Mapped[Optional[str]] = mapped_column(Text)
    artist_name: Mapped[Optional[str]] = mapped_column(Text)
    track_artist_name: Mapped[Optional[str]] = mapped_column(Text)
    composer: Mapped[Optional[str]] = mapped_column(Text)
    lyricist: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[str]] = mapped_column(Text)
    explicit: Mapped[Optional[str]] = mapped_column(Text)
    duration: Mapped[Optional[str]] = mapped_column(Text)
    label_name: Mapped[Optional[str]] = mapped_column(Text)
    total_author_right: Mapped[Optional[str]] = mapped_column(Text)
    right_id: Mapped[Optional[str]] = mapped_column(Text)
    author_right_1: Mapped[Optional[str]] = mapped_column(Text)
    ar_label_treaty_number_1: Mapped[Optional[str]] = mapped_column(Text)
    author_right_2: Mapped[Optional[str]] = mapped_column(Text)
    ar_label_treaty_number_2: Mapped[Optional[str]] = mapped_column(Text)
    author_right_3: Mapped[Optional[str]] = mapped_column(Text)
    ar_label_treaty_number_3: Mapped[Optional[str]] = mapped_column(Text)
    total_related_right: Mapped[Optional[str]] = mapped_column(Text)
    related_right_id_1: Mapped[Optional[str]] = mapped_column(Text)
    rr_label_treaty_number_1: Mapped[Optional[str]] = mapped_column(Text)
    related_right_id_2: Mapped[Optional[str]] = mapped_column(Text)
    rr_label_treaty_number_2: Mapped[Optional[str]] = mapped_column(Text)
    related_right_id_3: Mapped[Optional[str]] = mapped_column(Text)
    rr_label_treaty_number_3: Mapped[Optional[str]] = mapped_column(Text)
    types_of_rights: Mapped[Optional[str]] = mapped_column(Text)
    countries: Mapped[Optional[str]] = mapped_column(Text)
    create_date: Mapped[Optional[str]] = mapped_column(Text)
    release_date: Mapped[Optional[str]] = mapped_column(Text)
    sales_start_date: Mapped[Optional[str]] = mapped_column(Text)
    has_ringtone: Mapped[Optional[str]] = mapped_column(Text)
    ringtone_upc: Mapped[Optional[str]] = mapped_column(Text)
    ringtone_isrc: Mapped[Optional[str]] = mapped_column(Text)
    has_vclip: Mapped[Optional[str]] = mapped_column(Text)
    vclip_isrc: Mapped[Optional[str]] = mapped_column(Text)
    video_upc: Mapped[Optional[str]] = mapped_column(Text)
    has_lyrics: Mapped[Optional[str]] = mapped_column(Text)
    has_ttml: Mapped[Optional[str]] = mapped_column(Text)
    effective_date: Mapped[Optional[str]] = mapped_column(Text)
    termination_date: Mapped[Optional[str]] = mapped_column(Text)
    active_inactive: Mapped[Optional[str]] = mapped_column(Text)
    resource_reference: Mapped[Optional[str]] = mapped_column(Text)
    track_id: Mapped[Optional[str]] = mapped_column(Text)
    track_song_id: Mapped[Optional[str]] = mapped_column(Text)
    upload_id: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    track_name_norm_key: Mapped[Optional[str]] = mapped_column(Text)
    track_name_tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))


class StagingCatalogV2(Base):
    __tablename__ = 'staging_catalog_v2'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='staging_catalog_v2_pkey'),
        Index('idx_staging_v2_isrc', 'isrc'),
        Index('idx_staging_v2_upc', 'upc'),
        Index('idx_staging_v2_upload_id', 'upload_id')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, server_default=text('gen_random_uuid()'))
    loaded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    track_id: Mapped[Optional[str]] = mapped_column(Text)
    track_song_id: Mapped[Optional[str]] = mapped_column(Text)
    upc: Mapped[Optional[str]] = mapped_column(Text)
    isrc: Mapped[Optional[str]] = mapped_column(Text)
    track_name: Mapped[Optional[str]] = mapped_column(Text)
    genre_name: Mapped[Optional[str]] = mapped_column(Text)
    album_name: Mapped[Optional[str]] = mapped_column(Text)
    album_single: Mapped[Optional[str]] = mapped_column(Text)
    track_number: Mapped[Optional[str]] = mapped_column(Text)
    artist_name: Mapped[Optional[str]] = mapped_column(Text)
    track_artist_name: Mapped[Optional[str]] = mapped_column(Text)
    composer: Mapped[Optional[str]] = mapped_column(Text)
    lyricist: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[str]] = mapped_column(Text)
    explicit: Mapped[Optional[str]] = mapped_column(Text)
    duration: Mapped[Optional[str]] = mapped_column(Text)
    label_name: Mapped[Optional[str]] = mapped_column(Text)
    right_id: Mapped[Optional[str]] = mapped_column(Text)
    author_right_int: Mapped[Optional[str]] = mapped_column(Text)
    author_right_mob: Mapped[Optional[str]] = mapped_column(Text)
    author_right_pub: Mapped[Optional[str]] = mapped_column(Text)
    ar_label_treaty_number: Mapped[Optional[str]] = mapped_column(Text)
    related_right_id_int: Mapped[Optional[str]] = mapped_column(Text)
    related_right_id_mob: Mapped[Optional[str]] = mapped_column(Text)
    related_right_id_pub: Mapped[Optional[str]] = mapped_column(Text)
    rr_label_treaty_number: Mapped[Optional[str]] = mapped_column(Text)
    types_of_rights: Mapped[Optional[str]] = mapped_column(Text)
    countries: Mapped[Optional[str]] = mapped_column(Text)
    create_date: Mapped[Optional[str]] = mapped_column(Text)
    release_date: Mapped[Optional[str]] = mapped_column(Text)
    sales_start_date: Mapped[Optional[str]] = mapped_column(Text)
    has_ringtone: Mapped[Optional[str]] = mapped_column(Text)
    ringtone_upc: Mapped[Optional[str]] = mapped_column(Text)
    ringtone_isrc: Mapped[Optional[str]] = mapped_column(Text)
    has_vclip: Mapped[Optional[str]] = mapped_column(Text)
    vclip_isrc: Mapped[Optional[str]] = mapped_column(Text)
    video_upc: Mapped[Optional[str]] = mapped_column(Text)
    has_lyrics: Mapped[Optional[str]] = mapped_column(Text)
    has_ttml: Mapped[Optional[str]] = mapped_column(Text)
    effective_date: Mapped[Optional[str]] = mapped_column(Text)
    termination_date: Mapped[Optional[str]] = mapped_column(Text)
    active_inactive: Mapped[Optional[str]] = mapped_column(Text)
    resource_reference: Mapped[Optional[str]] = mapped_column(Text)
    upload_id: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    track_name_norm_key: Mapped[Optional[str]] = mapped_column(Text)
    track_name_tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))


class StagingPerson(Base):
    __tablename__ = 'staging_person'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='staging_person_pkey'),
        Index('idx_staging_person_staging_id', 'staging_id'),
        Index('idx_staging_person_upload_id', 'upload_id')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(CITEXT, nullable=False)
    staging_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    full_name_norm_key: Mapped[Optional[str]] = mapped_column(Text)
    tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    upload_id: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[Optional[str]] = mapped_column(Text)


t_staging_report = Table(
    'staging_report', Base.metadata,
    Column('row_number', Text),
    Column('label_own_code', Text),
    Column('isrc', Text),
    Column('track_name', Text),
    Column('artist_name', Text),
    Column('composer', Text),
    Column('lyricist', Text),
    Column('authors', Text),
    Column('author_share_pct', Text),
    Column('related_share_pct', Text),
    Column('play_count', Text),
    Column('payout_amount', Text),
    Column('price_per_play', Text),
    Column('service_name', Text),
    Column('upload_id', Text),
    Column('period', Text),
    Column('payout_amount_author', Text),
    Column('payout_amount_related', Text),
    Index('idx_staging_report_upload_id', 'upload_id')
)


class StagingReportAgg(Base):
    __tablename__ = 'staging_report_agg'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='staging_report_agg_pkey'),
        Index('idx_staging_report_agg_upload_id', 'upload_id'),
        Index('idx_staging_report_artist_key', 'artist_name_norm_key_full'),
        Index('idx_staging_report_auth_key', 'authors_norm_key_full'),
        Index('idx_staging_report_isfound', 'isfound', postgresql_where='(isfound = false)'),
        Index('idx_staging_report_track_key', 'track_name_norm_key')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    row_number: Mapped[Optional[int]] = mapped_column(Integer)
    label_own_code: Mapped[Optional[str]] = mapped_column(Text)
    isrc: Mapped[Optional[str]] = mapped_column(Text)
    track_name: Mapped[Optional[str]] = mapped_column(Text)
    track_name_norm_key: Mapped[Optional[str]] = mapped_column(Text)
    artist_name: Mapped[Optional[str]] = mapped_column(Text)
    authors: Mapped[Optional[str]] = mapped_column(Text)
    service_name: Mapped[Optional[str]] = mapped_column(Text)
    play_count: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    payout_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(20, 8), server_default=text('0.0'))
    price_per_play: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(20, 8), server_default=text('0.0'))
    isfound: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    artist_name_tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    artist_name_norm_key_full: Mapped[Optional[str]] = mapped_column(Text)
    authors_tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    authors_norm_key_full: Mapped[Optional[str]] = mapped_column(Text)
    upload_id: Mapped[Optional[str]] = mapped_column(Text)
  
    period: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payout_amount_author: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(precision=20, scale=8), server_default=text('0.0'), nullable=True )
    payout_amount_related: Mapped[Optional[decimal.Decimal]] = mapped_column( Numeric(precision=20, scale=8), server_default=text('0.0'), nullable=True)

    report_track_rights_cache: Mapped[list['ReportTrackRightsCache']] = relationship('ReportTrackRightsCache', back_populates='staging')


class StagingReportIds(Base):
    __tablename__ = 'staging_report_ids'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='staging_report_ids_pkey'),
        Index('idx_staging_report_ids_staging_id', 'staging_id'),
        Index('idx_staging_report_ids_track_id', 'track_id'),
        Index('idx_staging_report_ids_upload_id', 'upload_id')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    staging_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    track_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    finding_source: Mapped[Optional[int]] = mapped_column(Integer)
    upload_id: Mapped[Optional[str]] = mapped_column(Text)


class Track(Base):
    __tablename__ = 'track'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='track_pkey'),
        Index('idx_track_contribution_lookup', 'isrc', 'label_own_code', 'title'),
        Index('idx_track_isrc', 'isrc'),
        Index('idx_track_isrc_label_own_code', 'isrc', 'label_own_code'),
        Index('idx_track_label_own_code', 'label_own_code'),
        Index('idx_track_title', 'title'),
        Index('idx_track_title_norm_btree', 'title_norm_key'),
        Index('idx_track_title_norm_trgm', 'title_norm_key', postgresql_ops={'title_norm_key': 'gin_trgm_ops'}, postgresql_using='gin')

    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    isrc: Mapped[Optional[str]] = mapped_column(String(20))
    duration: Mapped[Optional[str]] = mapped_column(String(20))
    explicit: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    resource_reference: Mapped[Optional[str]] = mapped_column(Text)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    label_own_code: Mapped[Optional[str]] = mapped_column(String(50))
    title_tokens: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    title_norm_key: Mapped[Optional[str]] = mapped_column(Text)

    release: Mapped[list['Release']] = relationship('Release', secondary='track_release', back_populates='track',passive_deletes=True)
    track_contribution: Mapped[list['TrackContribution']] = relationship('TrackContribution', back_populates='track',passive_deletes=True)
    track_label: Mapped[list['TrackLabel']] = relationship('TrackLabel', back_populates='track',passive_deletes=True)
    report_track_rights_cache: Mapped[list['ReportTrackRightsCache']] = relationship('ReportTrackRightsCache', back_populates='track')
    track_right: Mapped[list['TrackRight']] = relationship('TrackRight', back_populates='track', passive_deletes=True )


t_track_full_info = Table(
    'track_full_info', Base.metadata,
    Column('id', BigInteger),
    Column('title', Text),
    Column('isrc', String(20)),
    Column('label_own_code', String(50)),
    Column('artist_name', Text),
    Column('composer', Text),
    Column('lyricist', Text),
    Column('authors', Text)
)





class Partners(Base):
    __tablename__ = 'partners'
    __table_args__ = (
        ForeignKeyConstraint(['right_usage_type_id'], ['right_usage_type.id'], name='partners_right_usage_type_id_fkey'),
        PrimaryKeyConstraint('id', name='partners_pkey'),
        UniqueConstraint('organization_name', 'service_name', name='partners_organization_name_service_name_key')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    right_usage_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_number: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    code: Mapped[Optional[str]] = mapped_column(String(50))

    right_usage_type: Mapped['RightUsageType'] = relationship('RightUsageType', back_populates='partners')
    report: Mapped[list['Report']] = relationship('Report', back_populates='partner')


class Release(Base):
    __tablename__ = 'release'
    __table_args__ = (
        ForeignKeyConstraint(['label_id'], ['label.id'], name='release_label_id_fkey'),
        PrimaryKeyConstraint('id', name='release_pkey'),
        UniqueConstraint('upc', name='release_upc_key'),
        Index('idx_release_upc', 'upc')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    upc: Mapped[Optional[str]] = mapped_column(String(20))
    release_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    label_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'Active'::character varying"))

    label: Mapped[Optional['Label']] = relationship('Label', back_populates='release')
    track: Mapped[list['Track']] = relationship('Track', secondary='track_release', back_populates='release')


class RightHolder(Base):
    __tablename__ = 'right_holder'
    __table_args__ = (
        ForeignKeyConstraint(['label_id'], ['label.id'], name='right_holder_label_id_fkey'),
        PrimaryKeyConstraint('id', name='right_holder_pkey'),
        UniqueConstraint('name', name='right_holder_name_key'),
        Index('idx_right_holder_name', 'name', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT, nullable=False)
    label_id: Mapped[Optional[int]] = mapped_column(Integer)
    effective_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    termination_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    label: Mapped[Optional['Label']] = relationship('Label', back_populates='right_holder')
    contract: Mapped[list['Contract']] = relationship('Contract', back_populates='right_holder')
    report_track_rights_cache: Mapped[list['ReportTrackRightsCache']] = relationship('ReportTrackRightsCache', back_populates='right_holder')
    track_right: Mapped[list['TrackRight']] = relationship('TrackRight', back_populates='right_holder')


class TrackContribution(Base):
    __tablename__ = 'track_contribution'
    __table_args__ = (
        ForeignKeyConstraint(['person_id'], ['person.id'], name='track_contribution_person_id_fkey'),
        ForeignKeyConstraint(['track_id'], ['track.id'], ondelete='CASCADE', name='track_contribution_track_id_fkey'),
        PrimaryKeyConstraint('id', name='track_contribution_pkey'),
        UniqueConstraint('track_id', 'person_id', 'role', name='track_contribution_unique_key'),
        Index('idx_tc_track_role_person', 'track_id', 'role', 'person_id'),
        Index('idx_track_contribution_person_id', 'person_id'),
        Index('idx_track_contribution_track_id', 'track_id')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    track_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    person_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    person: Mapped[Optional['Person']] = relationship('Person', back_populates='track_contribution')
    track: Mapped[Optional['Track']] = relationship('Track', back_populates='track_contribution')


class TrackLabel(Base):
    __tablename__ = 'track_label'
    __table_args__ = (
        ForeignKeyConstraint(['label_id'], ['label.id'], name='track_label_label_id_fkey'),
        ForeignKeyConstraint(['track_id'], ['track.id'], ondelete='CASCADE', name='track_label_track_id_fkey'),
        PrimaryKeyConstraint('id', name='track_label_pkey'),
        UniqueConstraint('track_id', 'label_id', name='track_label_track_id_label_id_key'),
        UniqueConstraint('track_id', 'label_id', name='track_label_unique_idx')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[Optional[int]] = mapped_column(Integer)
    label_id: Mapped[Optional[int]] = mapped_column(Integer)

    label: Mapped[Optional['Label']] = relationship('Label', back_populates='track_label')
    track: Mapped[Optional['Track']] = relationship('Track', back_populates='track_label')


class Contract(Base):
    __tablename__ = 'contract'
    __table_args__ = (
        ForeignKeyConstraint(['right_holder_id'], ['right_holder.id'], name='contract_right_holder_id_fkey'),
        PrimaryKeyConstraint('id', name='contract_pkey'),
        UniqueConstraint('treaty_number', name='contract_treaty_number_key')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    treaty_number: Mapped[str] = mapped_column(String(255), nullable=False)
    right_holder_id: Mapped[Optional[int]] = mapped_column(Integer)
    effective_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    termination_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    right_holder: Mapped[Optional['RightHolder']] = relationship('RightHolder', back_populates='contract')
    track_right: Mapped[list['TrackRight']] = relationship('TrackRight', back_populates='contract')


class Report(Base):
    __tablename__ = 'report'
    __table_args__ = (
        ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE', name='report_partner_id_fkey'),
        ForeignKeyConstraint(['right_category_id'], ['right_category.id'], name='report_right_category_id_fkey'),
        ForeignKeyConstraint(['right_usage_type_id'], ['right_usage_type.id'], name='report_right_usage_type_id_fkey'),
        PrimaryKeyConstraint('id', name='report_pkey')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_usage_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_month: Mapped[int] = mapped_column(Integer, nullable=False)
    report_year: Mapped[int] = mapped_column(Integer, nullable=False)
    play_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    payout_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(20, 4), server_default=text('0.0'))
    price_per_play: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(20, 6), server_default=text('0.0'))
    upload_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    partner: Mapped['Partners'] = relationship('Partners', back_populates='report')
    right_category: Mapped['RightCategory'] = relationship('RightCategory', back_populates='report')
    right_usage_type: Mapped['RightUsageType'] = relationship('RightUsageType', back_populates='report')
    report_track_rights_cache: Mapped[list['ReportTrackRightsCache']] = relationship('ReportTrackRightsCache', back_populates='report')


t_track_release = Table(
    'track_release', Base.metadata,
    Column('track_id', Integer, primary_key=True),
    Column('release_id', Integer, primary_key=True),
    ForeignKeyConstraint(['release_id'], ['release.id'], ondelete='CASCADE', name='track_release_release_id_fkey'),
    ForeignKeyConstraint(['track_id'], ['track.id'], ondelete='CASCADE', name='track_release_track_id_fkey'),
    PrimaryKeyConstraint('track_id', 'release_id', name='track_release_pkey'),
    Index('idx_track_release_release_id', 'release_id'),
    Index('idx_track_release_track_id', 'track_id')
)


class ReportTrackRightsCache(Base):
    __tablename__ = 'report_track_rights_cache'
    __table_args__ = (
        ForeignKeyConstraint(['report_id'], ['report.id'], ondelete='CASCADE', name='fk_report'),
        ForeignKeyConstraint(['right_category_id'], ['right_category.id'], name='fk_right_category'),
        ForeignKeyConstraint(['right_holder_id'], ['right_holder.id'], name='fk_right_holder'),
        ForeignKeyConstraint(['right_usage_type_id'], ['right_usage_type.id'], name='fk_right_usage_type'),
        ForeignKeyConstraint(['staging_id'], ['staging_report_agg.id'], ondelete='SET NULL', name='fk_staging_report'),
        ForeignKeyConstraint(['track_id'], ['track.id'], name='fk_track'),
        PrimaryKeyConstraint('id', name='report_track_rights_cache_pkey'),
        Index('idx_report_track_rights_report_id', 'report_id'),
        Index('idx_report_track_rights_track_id', 'track_id')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    right_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_usage_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_holder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    share_percentage: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    report_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    staging_id: Mapped[Optional[int]] = mapped_column(Integer)

    report: Mapped[Optional['Report']] = relationship('Report', back_populates='report_track_rights_cache')
    right_category: Mapped['RightCategory'] = relationship('RightCategory', back_populates='report_track_rights_cache')
    right_holder: Mapped['RightHolder'] = relationship('RightHolder', back_populates='report_track_rights_cache')
    right_usage_type: Mapped['RightUsageType'] = relationship('RightUsageType', back_populates='report_track_rights_cache')
    staging: Mapped[Optional['StagingReportAgg']] = relationship('StagingReportAgg', back_populates='report_track_rights_cache')
    track: Mapped['Track'] = relationship('Track', back_populates='report_track_rights_cache')


class TrackRight(Base):
    __tablename__ = 'track_right'
    __table_args__ = (
        CheckConstraint('share_percentage >= 0::numeric AND share_percentage <= 100::numeric', name='track_right_share_percentage_check'),
        ForeignKeyConstraint(['contract_id'], ['contract.id'], name='track_right_contract_id_fkey'),
        ForeignKeyConstraint(['region_id'], ['region.id'], name='track_right_region_id_fkey'),
        ForeignKeyConstraint(['right_category_id'], ['right_category.id'], name='track_right_right_category_id_fkey'),
        ForeignKeyConstraint(['right_holder_id'], ['right_holder.id'], name='track_right_right_holder_id_fkey'),
        ForeignKeyConstraint(['right_usage_type_id'], ['right_usage_type.id'], name='track_right_right_usage_type_id_fkey'),
        ForeignKeyConstraint(['track_id'], ['track.id'], ondelete='CASCADE', name='track_right_track_id_fkey'),
        PrimaryKeyConstraint('id', name='track_right_pkey'),
        Index('idx_track_right_right_holder_id', 'right_holder_id'),
        Index('idx_track_right_track_id', 'track_id')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    track_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contract_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    right_holder_id: Mapped[Optional[int]] = mapped_column(Integer)
    right_category_id: Mapped[Optional[int]] = mapped_column(Integer)
    share_percentage: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    right_usage_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    region_id: Mapped[Optional[int]] = mapped_column(Integer)
    region: Mapped[Optional[str]] = mapped_column(String(30))

    contract: Mapped[Optional['Contract']] = relationship('Contract', back_populates='track_right')
    region_: Mapped[Optional['Region']] = relationship('Region', back_populates='track_right')
    right_category: Mapped[Optional['RightCategory']] = relationship('RightCategory', back_populates='track_right')
    right_holder: Mapped[Optional['RightHolder']] = relationship('RightHolder', back_populates='track_right')
    right_usage_type: Mapped[Optional['RightUsageType']] = relationship('RightUsageType', back_populates='track_right')
    track: Mapped['Track'] = relationship('Track', back_populates='track_right')

class UITrackDraft(Base):
    __tablename__ = 'ui_track_drafts'
    __table_args__ = (
        ForeignKeyConstraint(['track_id'], ['track.id'], ondelete='CASCADE', name='ui_track_drafts_track_id_fkey'),
        PrimaryKeyConstraint('id', name='ui_track_drafts_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'draft'"))
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # Set when this draft edits an existing track (as opposed to creating a new one).
    track_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))


class ReportTrackRightsDistribution(Base):
    __tablename__ = 'report_track_rights_distribution'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    staging_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    track_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    right_holder_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    right_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_usage_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    original_share_percentage: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    calculated_share_percentage: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    final_payout_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    is_normalized: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('FALSE'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))