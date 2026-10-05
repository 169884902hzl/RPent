# 3670 report7 append-only intermediate statistics

Report6 retained unchanged (183 rows); report7 adds 36 closed rows for cumulative 219/400.

| New arm | rows | sustained during | sustained at end | target truth | failure counts |
|---|---:|---|---|---|---|
| frypan/handle_full_subtask160 | 22 | {'False': 10, 'True': 12} | {'False': 22} | {'False': 11, 'True': 11} | {'no_sustained_grasp_during_subtask': 10, 'target_satisfied': 11, 'sustained_grasp_then_released_target_not_satisfied': 1} |
| moka pot/centre_full_subtask160 | 11 | {'False': 7, 'True': 4} | {'False': 11} | {'False': 8, 'True': 3} | {'no_sustained_grasp_during_subtask': 7, 'target_satisfied': 3, 'sustained_grasp_then_released_target_not_satisfied': 1} |
| moka pot/handle_full_subtask160 | 3 | {'False': 2, 'True': 1} | {'False': 3} | {'False': 3} | {'no_sustained_grasp_during_subtask': 2, 'sustained_grasp_then_released_target_not_satisfied': 1} |

## New rows

- `moka_handle_full_libero_10_t2_s12_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `4d0d783ee7c54218aa3d83df8a9bcf42678d6680091eaed13cda7acd693b5648`
- `moka_handle_full_libero_10_t2_s16_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `2b40e4cec6fc18dc207cfadec86a45ee5008a848e230ad8766ac9ec2d54045dc`
- `moka_handle_full_libero_10_t2_s20_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `22df93d0448130bdaa29f938273f142ea441ead15fc91a38cb0ebdd64b79f053`
- `pan_handle_full_libero_10_t2_s18_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `c32d10c7c693208c5a0a22a8038fd3bc1f0ea9de6aaf2c22f42ac347ff7377e1`
- `pan_handle_full_libero_10_t2_s22_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `87f6f389efb7c131082778c7532114b39cbfb54f42d4ea84daf01b9dadbac447`
- `pan_handle_full_libero_10_t2_s26_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `0ee68e78a478d4ba2b515845d8631807f368781a5a592b08636fc262dbcbcef3`
- `pan_handle_full_libero_10_t2_s30_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `da8d5b141e59d84330cf602a862b2d7e8518ac5f6480ff5e98a80ccf9e26036a`
- `pan_handle_full_libero_10_t2_s34_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `0cfd2abf5b9be5e6c0e5979867eeea1ca3876971af8bd3d088d5cd1bac03dfa4`
- `pan_handle_full_libero_10_t2_s38_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `9e5eeed3f9cc6bd669595da5c3a55aef762a1bc65c2cab6d6941b36fb1767fdd`
- `moka_handle_full_libero_10_t2_s17_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `2cfecb2f125fc2b7a69ef14ccefdd796494cc94fb6e06988e12c10f48c211075`
- `moka_handle_full_libero_10_t2_s21_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `f1dbc375946d4885c80d2f894b6440ce77d2f2570a4ba6e625e69cc5284d04b3`
- `pan_handle_full_libero_10_t2_s15_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `5d97fe817dbd8df15980f22cfccdbdc74b542ed22fa18d103ec8f7c80bf100dd`
- `pan_handle_full_libero_10_t2_s19_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `84de897bfcefd630ef4bfecc3024166e90d1959c9d016d41b0af49357c8a94c7`
- `pan_handle_full_libero_10_t2_s23_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `fc36ade4ef5108b6ce0d4cab1b2ce85395ff226faf1ba10a4c4f586bb258ba75`
- `pan_handle_full_libero_10_t2_s27_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `090d57e685733c03ac9b072fe021cf1b5f00487e8f96d18acaeaedf92c2c512a`
- `pan_handle_full_libero_10_t2_s31_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `7d2d014e7ca301bb158637f5ac6b104a383201f9143ab360737ea1437663a2a7`
- `pan_handle_full_libero_10_t2_s35_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `eda90275126c4d1b1f63803053e78de116e7bf38aa0f3ad35de3cb89d3e6a438`
- `pan_handle_full_libero_10_t2_s39_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `bee46f258c831033cf44ad7e8390c177bc49037983bc073ee156b97fdc7d554e`
- `moka_handle_full_libero_10_t2_s10_r0_centre_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `9f2a3eaff2380f4cadec8f693547fad5b97c30010a2f567bb2026e8f5e8d2f6f`
- `moka_handle_full_libero_10_t2_s14_r0_centre_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `5f036439691dd38fbee45d8c0836b59fcb6a82aa95f125bc0094930f79ba7ca3`
- `moka_handle_full_libero_10_t2_s18_r0_centre_full_subtask160`: during=True, target=False, failure=sustained_grasp_then_released_target_not_satisfied; choices SHA `1a5a7b7126400c4d6f7bd2d756d27d34e0de0985aa90d3452aafca63ebf89309`
- `pan_handle_full_libero_10_t2_s16_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `e7ec9b9ca7305e7608adc72a3baeeabf8fe6d83777d5f033e3e5355e7b6295b6`
- `pan_handle_full_libero_10_t2_s20_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `f19474f04c5a3ac5048bce6dbce3005aa3294116b5a13547126f801df70af175`
- `pan_handle_full_libero_10_t2_s24_r1_handle_full_subtask160`: during=True, target=False, failure=sustained_grasp_then_released_target_not_satisfied; choices SHA `cee8c0dd53182cf960e9c25ea172e604c268d3632f846e4b94465602729d54b9`
- `pan_handle_full_libero_10_t2_s28_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `a447b35e3cf9beeb336343d2e7ea6550f2ede6398c27ab172e2055000c6711a7`
- `pan_handle_full_libero_10_t2_s32_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `c516ee1d931e435e756b61912ea0cfdc5e8701ac55ccb93f54d69f8894f90b09`
- `pan_handle_full_libero_10_t2_s36_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `7a30e79327ec14fb9d679c013199996d30f499ce6177391dddb3159618884555`
- `pan_handle_full_libero_10_t2_s40_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `3de3e0e273aa3310a1261332da7cfdc1320bfa5a97da4798695b1a5ff2081aab`
- `moka_handle_full_libero_10_t2_s11_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `e25f809362b9bddc4b649498913c543c8f6fcc5214ac6ca148abe8091fd70c19`
- `moka_handle_full_libero_10_t2_s15_r0_centre_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `3b70e3658634becb71446bb2bd538eaa8563932536aa66589725a2863dce1276`
- `moka_handle_full_libero_10_t2_s19_r0_centre_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `7793742cbd342df62452e8f86bd86e1386d97ca12713f20a357beb0785cb0a73`
- `pan_handle_full_libero_10_t2_s45_r1_handle_full_subtask160`: during=True, target=True, failure=target_satisfied; choices SHA `7e14b3670a355eb44c711f9a3eaffd4a5761387c1fc2341a923b538288a26cec`
- `pan_handle_full_libero_10_t2_s49_r1_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `9369d468b7ae57dde5da836d0f2e9d26158924a77ba803e69186401b545128f2`
- `moka_handle_full_libero_10_t2_s3_r0_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `1be9b05dac4e6888998d61a6c80abfd3a6212c8e9c25f186e5b144453aabfce6`
- `moka_handle_full_libero_10_t2_s7_r0_handle_full_subtask160`: during=True, target=False, failure=sustained_grasp_then_released_target_not_satisfied; choices SHA `070a18cf92eded92b03136488810aecbccc3eaa665506bcb248f69ededf7127e`
- `moka_handle_full_libero_10_t2_s11_r0_handle_full_subtask160`: during=False, target=False, failure=no_sustained_grasp_during_subtask; choices SHA `e95242b0d8c170514b118e15567808a827c83f112e57c054c9ba4e24a734782b`

## New moka-handle rows

The three newly closed handle rows all executed 160 chunks; no not-executed or handle-measurement-missing row is silently counted as a physical failure. Two have known no-sustained-grasp evidence; one has known sustained grasp during transfer but false target predicate. Public placement unknown remains unknown.

| Seed | Execution | Physical grasp evidence | Target truth | Public place | Actions/chunks |
|---:|---|---|---|---|---:|
| 3 | executed | known_no_sustained_grasp | False | None | 852/160 |
| 7 | executed | known_sustained_grasp_target_false | False | False | 853/160 |
| 11 | executed | known_no_sustained_grasp | False | None | 854/160 |

## Cumulative unchanged accounting

The upstream current prefix auditor checked 219 choices files with 0 mismatches. Report6's 183 choices and all row fields match byte-for-byte at the JSON value level. Cumulative arm summaries, including independent repetition-0 selection, Wilson intervals and unknown denominators, are copied from the upstream report7 auditor output.

The old 3670 private truth definition remains active for this report. The new v2 support rule is code-only and does not relabel report6 or report7.

Report SHA256: 21f2a4d0255c187324202fd7910714b01b157e312365fed475a270612c132932
