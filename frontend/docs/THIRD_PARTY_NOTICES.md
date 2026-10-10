# Third party and licensing notes

## Project license

The repository contains an MIT license. Figma's [AI Terms](https://www.figma.com/legal/ai-terms/) say generated output is Customer Content and that, between Figma and the customer, the customer retains its rights in that output. Figma's [Make FAQ](https://help.figma.com/hc/en-us/articles/31722591905559-Figma-Make-FAQs) also notes that a Make prototype may incorporate third party fonts, code, or images. The project source can therefore be distributed under the repository's MIT license only to the extent the project owner has rights to license that source and its included material.

## Third party software and fonts

The installed lockfile dependency tree contains 43 distinct package name/version pairs on Windows: 36 report MIT, 2 Apache-2.0, 2 ISC, 2 MPL-2.0, and 1 BSD-3-Clause in package metadata. No installed package had an unspecified license identifier. The two MPL-2.0 packages are lightningcss@1.32.0 and lightningcss-win32-x64-msvc@1.32.0, used in the build toolchain. Keep their license and copyright notices when redistributing those package files; consult the [Mozilla Public License 2.0](https://www.mozilla.org/en-US/MPL/2.0/) for its file-level terms. The lockfile has 92 entries, including platform-specific packages not installed on this machine, so repeat this review for the target release platform.

Each package remains subject to its own upstream license and copyright notices. Preserve these notices when redistributing package files or bundled output; the repository's MIT license does not replace third party licenses.

Pretendard is loaded remotely from jsDelivr by src/index.css; no font binaries are stored in this repository. The upstream project states that Pretendard is distributed under the SIL Open Font License 1.1. See the [Pretendard license information](https://github.com/orioncactus/pretendard/blob/main/packages/pretendard/docs/en/README.md) and [upstream license file](https://github.com/orioncactus/pretendard/blob/main/LICENSE).
