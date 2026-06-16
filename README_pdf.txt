README
リリースROMのfor_debugフォルダ内にある次のイメージ郡(以下、debuggableイメージ郡)に
ついて本資料で説明します。
boot-debug.img (P8以降は、init_boot-debug.img)
boot-debug_ski.img

◆◆ショートカット◆◆
userビルドROMでroot権限が取得したい方はこちらから、boot-debug.img (P8以降は、
init_boot-debug.img) へ書換えを行ってください。

目次
debuggableイメージ郡について
書換え方法
実機にdebuggableイメージが書かれているかどうかの確認方法について
boot-debug.img (P8以降は、init_boot-debug.img)
boot-debug_ski.img
boot.imgのpack/unpack手順について
問い合わせ先

debuggableイメージ郡について
image

summary

boot-debug.img

後述するデバッグ機能を有したboot.img

init_boot-debug.img

後述するデバッグ機能を有したboot.img ※P8以降はこちら

!!!注意!!!
debuggableイメージ郡の位置づけは、あくまでデバッグ用の特ロムです
もしも、この特ロムで発生した不具合についてバグ起票する場合は、必ず特ロムであるこ
とを明記ください
端末にdebuggableイメージ郡が焼かれているかの確認方法は、こちらを参照して確認して
ください

書換え方法
boot-debug.img (P8以降は、init_boot-debug.img) への書換え方法につい
て
debuggableイメージ群への書換えは、SHDLで書き換える前に以下手順を実施する必要が有り
ます。
※Android-R以降のモデルについて※
P3dR, C2R機種をはじめとするVF(vendor freeze)モデルを考慮し、イメージとスクリプト類をフ
ォルダ分けしています。 直近モデルではfor_debugフォルダ内にもスクリプト類が格納され、
混在する形となりますが、for_debug_s配下にあるスクリプトを利用してください。
Directory
for_debug
for_debug_s

Summary
boot-debug.img (P8以降は、init_boot-debug.img), abl-debug_ <sku> .elf
(P8以降は、abl-debug廃止) を格納
上記以外のbatファイルやスクリプト類を格納

＜書き換え手順＞

!!!注意!!!
「vbmeta/vbmeta_systemでの認証対象イメージ」を単一のイメージと差し替える場合は、
boot-debug_change.bat実施後に、vbmetaをvbmeta_verification_disabled.imgに差し替える必要
があります。
※こちらはboot-debug_change.batにて、boot-debug.img (P8以降は、init_boot-debug.img) 用の
vbmetaに差し替えている機種が存在するためとなります。
※差し替えが必要なのは、単一のイメージと差し替えることで、AVB認証エラーが発生するためであ
り、
vbmetaもしくはvbmeta_systemを含めたローカルでビルドしたROM一式 を差し替える分には問題はあ
りません。
※「vbmeta/vbmeta_systemでの認証対象イメージ」については、
tools(_xxx).zipに内包しているavbtoolにて、vbmeta/vbmeta_systemの情報を確認することで確
認可能です。（LinuxPCで実施が必要です。）
$./avbtool info_image --image [image名（vbmeta/vbmeta_systemのイメージ名）]
P7であれば、以下イメージが該当いたします。
・vendor.img/odm.img/vendor_dlkm.img/odm_dlkm.img/boot.img/dtbo.img/vendor_boot.img
・system.img/system_ext.img/product.img

P8以降は、Pre-MP(旧PVT)実機(bootloaderがlock)の場合は、事前にunlock
してください！
①A版(userdebug)のROMに書き換える
②下記アプリをインストールする
\\hfs.win.sharp.co.jp\H01_SoftCommon\hrow010_Partner\P1\共通\document\04_システム\00_
ギルド\11_boot_debuggable\90_ツール\OEMロック設定可能化アプリ
---------> adb install ForceEnableOemUnlockByUser.apk
---------③②でインストールした「EnableOemUnlock」アプリを起動し。[ALLOW]をタップする
④開発者向オプションを起動し、[OEMロック解除]をONにする
⑤fastboot起動する
---------> adb reboot bootloader
---------⑥bootloaderの状態を確認
---------> fastboot getvar unlocked
unlocked: no
---------※unlocked: yesの場合は、この手順は不要
⑦bootloaderをunlockする
---------> fastboot flashing unlock
---------コマンド実行後、↓キー、電源キーの順に押すと、再起動がかかる
⑧これでunlockされたため、確認したいROM(A版以外でもOK)に書き換える
※SHDLで書き換えてもunlock状態は保持される。
★使用が終了したら、lock戻すことを忘れずに！
⑨再び、A版(userdebug)のROMに書き換える
⑩fastboot起動する
---------> adb reboot bootloader
---------⑪bootloaderをlockする
---------> fastboot flashing lock
---------コマンド実行後、↓キー、電源キーの順に押すと、再起動がかかる
⑫再起動後、lock状態に戻ります

1. for_debug_sフォルダ内にあるboot_debug_change.batを実行する
対応するdebuggableイメージが元のイメージと置き換わります
ROMフォルダ直下に「※boot-debugに差し替え中」というファイルも作成されます
元のイメージはboot_org.imgにリネームされ、for_debugフォルダに退避されます
2. SHDLでロム書換えする ※ SHDLに「ライトプロテクト解除」コマンドが存在する場合は、
ロム書き換え後に実行。
3. 端末起動させ、PCとUSB接続
4. for_debug_sフォルダ内にあるmount_scratch.batを実行する
5. 以下出力されたら完了
===== Complete ====

実機にdebuggableイメージが書かれているかどうかの確認方
法について
下記の方法でboot-debug.img (P8以降は、init_boot-debug.img)が実機に書かれているかどうか
を確認できます。

システムプロパティから確認する方法
1. 下記コマンドを実行
$ adb shell getprop

2. 以下対応表より判別可能
image
boot-debug.img (P8以降は、init_bootdebug.img)

ro.sharp.rooted

ro.debuggable

1

1

※android T以降で、ro.debuggable=0かつrootが取れるROMで確認したい場合は、下記の
ROMを使用してください。

\\hfs.win.sharp.co.jp\F01_Release\aosp_ea_[OS名]\Release\[PF名]\for_monitor_test

boot-debug.img (P8以降は、init_boot-debug.img)
通常のリリースROMに以下修正を加えた不具合解析用のイメージです。通常ROMではセキュリ
ティ上できないことをいくつか可能にしています。
USBデバッグのデフォルト有効化
起動ログ出力
tcpdumpログ取得
SSL/TLS通信復号化について
fastbootモードの有効化

USBデバッグのデフォルト有効化
userビルドでも初回起動時からADBを有効にする対応です。

起動ログ出力
端末起動時からのカーネルログ、logcatを端末内に保存することができます。
＜有効化手順＞
1. 下記コマンドを実行
$ adb root
■ ↓A版では不要↓ ■
$ adb shell mount -o rw,remount /system
$ adb push logcatd /system/bin
$ adb push logcatd.rc /system/etc/init
■ ↑A版では不要↑ ■
$ adb shell setprop persist.logd.logpersistd logcatd
$ adb reboot

2. 「/data/misc/logd」配下にログが格納される（ログファイル名：logcat.N）
＜無効化手順＞
1. 下記コマンドを実行
$ adb root
$ adb shell setprop persist.logd.logpersistd ""
$ adb reboot

tcpdumpログ取得
ネットワーク通信ログを取得することができます。 取得した生データは、WireSharkなどのパ
ケット通信解析ツールを用いることで解析が可能です。
＜ログ取得方法＞
1. 端末の機内モードをONにする *
2. 下記コマンドを実行
$ adb shell "tcpdump -i any -s0 -S -w /data/local/tmp/tcpdump.cap &"
→/data/local/tmp/tcpdump.capにtcpdumpログが保存されます

3. 端末の機内モードをOFFにする *
*: 機内モードON→OFFの手順は必須ではありませんが、こうすることでDNS通信をログに残し
ておくことででき、 Wiresharkでログ参照する際に名前解決された状態でtcpdumpログの確認
が可能となるメリットがあります

SSL/TLS通信復号化について
androidTからは動作非サポートとしております。
以下は参考情報としてAndroidS時の対応を記載致します。
AndroidT以降は以下を参考に、AndroidOS差分に追従してご利用ください。
■参考情報
http://10.24.71.91/gerrit/c/PCQ/platform/external/boringssl/+/77309
http://10.24.71.91/gerrit/c/PCQ/platform/external/boringssl/+/77310
http://10.24.71.91/gerrit/c/PCQ/platform/external/boringssl/+/77402
また、端末のAPEX設定がupdatableである場合は、
以下のシェルを参考に、libssl_debug.soを差し替えたapexファイルを作成する必要があります。
http://10.24.71.91/gerrit/plugins/gitiles/sharp/vendor/sharp/commonsys-intf/imageutils/+/refs/heads/S/AQUOS/MASTER/boot-debug/create_conscrypt_apex.sh
■端末のAPEX設定の確認方法
$ adb shell ls -l /system/apex
→xxxx.conscryptディレクトリが格納されている：flatten
→xxxx.conscrypt.apexが格納されている：updatable
→/system/apex自体がない or 上記以外：対応不可

fastbootモードの有効化
userビルドでも、以下いずれかの手順でfastboot起動へ遷移することができます。
キーコンビによるfastboot起動(↑＋電源キー)
通常起動後、以下コマンドを実行
$ adb reboot bootloader

boot-debug_ski（SharpKernelImage）.img
init_boot.img非搭載機種の場合
boot-debug.imgにローカルビルドしたkernelを加えた不具合解析用のイメージです。
従来のA版相当であるkernelが搭載されており、例として以下CONFIG等が有効となります。
boot-debug_ski.imgをboot-debug.imgに差し替え、boot-debug.img (P8以降は、init_bootdebug.img) への書換え方法についてで焼き変えてご利用ください。
CONFIG_DEVMEM
CONFIG_ANDROID_ENGINEERING

init_boot.img搭載機種の場合(for_debug下にsystem_dlkmフォルダが存在し
ない機種)
boot-debug.img廃止に伴い、boot.img(GKI)にローカルビルドしたkernelを加えたイメージとな
ります。
boot-debug_ski.imgをboot.imgに差し替え、SHDL等で焼き替えてご利用ください。
debuggable機能が必要な場合、boot-debug.img (P8以降は、init_boot-debug.img) への書換え
方法についてで焼き変えてご利用ください。

init_boot.img搭載機種の場合(for_debug下にsystem_dlkmフォルダが存在す
る機種)
boot-debug.img廃止に伴い、boot.img(GKI)にローカルビルドしたkernelを加えたイメージとな
ります。
加えて以下手順が必要となっております。
1. 通常通りSHDL等で焼き替え (init_boot-debugの機能が必要な場合はboot-debug.img (P8以
降は、init_boot-debug.img) への書換え方法についてを参照)
2. for_debug_sフォルダにてboot_debug_change.bat実行後、mount_scratch.batを実行 (1.で
init_boot-debug.imgを書き換えていた場合はboot_debug_change.batの実行は不要)
3. for_debugフォルダにて以下コマンドを実行し、boot-debug_ski.imgを書き換え

$ adb root
$ adb shell mount -o rw,remount /system_dlkm
$ adb push system_dlkm/lib /system_dlkm/
$ adb reboot fastboot
$ fastboot flash boot boot-debug_ski.img
$ fastboot reboot

boot.imgのpack/unpack手順について
ROMフォルダのtools_vendor.zipの中にある unpack_bootimg を使用して、boot.imgの分解・結
合することができます。 ここではboot.imgを例に説明しますが、同様の操作を行うことで

vendor_boot.img, recovery.imgも分解・結合が可能です。 なおLinuxPCでの手順であり、記載し
ているコマンド例はカレントディレクトリが tools/bin であることを前提としています。

＜分解手順(unpack)＞
1. 下記コマンドを実行する。結合手順(pack)で必要となるので出力内容を記録しておくこと
$ ./unpack_bootimg --boot_img <boot.imgのファイル> --format mkbootimg --out <出力デ
ィレクトリ>
--header_version 3 --os_version 11.0.0 --os_patch_level 2021-05 --kernel <出力ディ
レクトリ>/kernel --ramdisk <出力ディレクトリ>/ramdisk --cmdline ''
↑記録する

2. 以下ファイルが生成されるので状況に応じて改変する。
【kernelの差し替え】
kernel-objectを改変する場合、ローカルビルドしたkernel-objectに差し替える
$ cp .../out/target/product/XXXX/kernel <出力ディレクトリ>/kernel

【ramdiskの改変】
ramdisk内のprop.defaultを改変する場合、ramdiskを展開した後にテキストエディ
タで直接修正する。圧縮形式により手順が異なることに注意

# 圧縮形式を確認
$ file <出力ディレクトリ>/ramdisk
ramdisk: gzip compressed data, from Unix
ramdisk: LZ4 compressed data (v0.1-v0.9)

←GZIP形式
←LZ4形式

# ramdisk.rawを生成
# GZIP形式の場合
$ ./gzip -c <出力ディレクトリ>/ramdisk > ramdisk.raw
# LZ4形式の場合
$ ./lz4 -c -d <出力ディレクトリ>/ramdisk > ramdisk.raw
# rootディレクトリにramdisk内容を展開
$ mkdir out_ramdisk
$ cd out_ramdisk
$ cpio -i < ../ramdisk.raw
$ gedit prop.default

改変後、再度ramdiskイメージを作成する
# GZIP形式の場合
$ ./mkbootfs -d ../fs_config out_ramdisk | ./gzip > ramdisk.new
# LZ4形式の場合
$ ./mkbootfs -d ../fs_config out_ramdisk | ./lz4 -l -12 --favor-decSpeed >
ramdisk.new

作成したramdiskに差し替える
$ cp ramdisk.new <出力ディレクトリ>/ramdisk

＜結合手順(pack)＞
1. 下記コマンドを実行
$ ./mkbootimg -o boot_new.img <分解時に記録した出力内容>
# 今回例の場合
$ ./mkbootimg -o boot_new.img --header_version 3 --os_version 11.0.0 -os_patch_level 2021-05 --kernel <出力ディレクトリ>/kernel --ramdisk <出力ディレクト
リ>/ramdisk --cmdline ''

TIPS
・ fastboot用ドライバのインストール手順
1. fastbootバージョンは最新としておくこと
https://developer.android.com/studio/releases/platform-tools?hl=en
2. 実行前に以下のドライバをインストールしておくこと
<1> https://developer.android.com/studio/run/win-usb?hl=en
<2> \\hfs.win.sharp.co.jp\H01_SoftCommon\hrots400_Partner\NB\共通
\Tool\USBdriver\adb\20210715_usb_driver_r07-windows

問い合わせ先
sbchro-and-sys@list.sharp.co.jp までご連絡ください。
Last update: 2023/04/18

