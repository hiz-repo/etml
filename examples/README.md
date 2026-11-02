# Examples

Project-authored ETML markup uses the [MIT License](../LICENSE). The stories include editorial emotion and narrative annotations.

<a id="mikan"></a>

## [蜜柑 (Mikan)](mikan.etml)

- Author: 芥川龍之介 (Ryūnosuke Akutagawa).
- Source: [Aozora Bunko, No. 98](https://www.aozora.gr.jp/cards/000879/files/98_15272.html).
- Base edition: 『現代日本文学大系 43 芥川龍之介集』, 筑摩書房, 1968.
- Transcription: j.utiyama. Proofreading: 野口英司.
- Text: Public domain in Japan.

<a id="the-gift-of-the-magi"></a>

## [The Gift of the Magi](the_gift_of_the_magi.etml)

- Author: O. Henry.
- Source acknowledgement: [Project Gutenberg, eBook No. 7256](https://www.gutenberg.org/ebooks/7256).
- Electronic text: Susan Ritchie. HTML: Jose Menendez.
- Text: Public domain in the United States.

## Check the annotations

From the repository root:

```sh
python3 scripts/check_story_examples.py --tests
```

The script checks structure, preserved prose, and lossless serialization. Add `--show` to inspect annotated ranges.
