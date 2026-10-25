# SoundCloud download handling

The reported message for track 256277192 says its stream is DRM protected. This update **does not decrypt or bypass DRM**. The old hint incorrectly named Widevine/PlayReady regardless of what the extractor actually established; the new message does not guess a scheme.

## Implemented behavior

1. Try the existing normal SoundCloud metadata/available-format path.
2. When yt-dlp reports DRM, do not repeatedly retry the same protected direct download with cosmetic retry flags.
3. If ordinary metadata extraction failed, attempt **public metadata only** with `--skip-download --ignore-no-formats-error --print title/duration/uploader`. This can retrieve metadata even when no playable unprotected format exists. The option is never used for media download and does not enable decryption.
4. Only when real title/uploader metadata is available, use the existing title/artist/version/duration-verified alternate-source search. No title is guessed from the URL or track ID; NA/empty metadata is rejected. Existing preview rejection and duration checks remain.
5. A successful alternate result now exposes the **actual alternate source URL** and a note explaining that the SoundCloud stream was not downloaded and DRM was not decrypted. Metadata verification is not a rights/authorization guarantee.
6. Otherwise stop with a concise explanation directing the user to the creator's enabled download or another authorized non-DRM source.

No decryption keys, DRM tools, unplayable-format download flag, or protected-stream extraction was added. Cookies still only support the pre-existing authorized-session functionality; they are not presented as DRM decryption.

## Validation and limitations

Unit tests cover metadata-only recovery with and without an alternate, the real-source disclosure, direct DRM failure without futile direct retries, refusal to search without metadata, and removal of invented scheme names from the hint. Existing downloader tests also pass.

This environment permits GitHub/package-registry traffic but not live SoundCloud/YouTube/recognition endpoints. Therefore the specific reported track was **not live-tested**, and a working full copy is not promised. The metadata-only step can also fail depending on site behavior or yt-dlp version. Update yt-dlp normally on the bot host and test with a URL you are authorized to download; if only a protected stream exists, the bot will still refuse it.
