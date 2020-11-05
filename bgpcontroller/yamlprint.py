import os.path
import yaml
from argparse import ArgumentParser

if __name__ == '__main__':
    parser = ArgumentParser("YamlTest")
    parser.add_argument("conf_file", metavar="config_file", type=str,
                        help="Path to the configuration file")
    args = parser.parse_args()

    with open(args.conf_file, "r") as stream:
        config = yaml.safe_load(stream)

    print(config)
    print(config["bgpspeakers"])
    print("\n")
    for speaker in config["bgpspeakers"]: 
        speaker_cfg = config["bgpspeakers"][speaker]
        print(speaker_cfg)
        print("\n")
        for peer in speaker_cfg["peers"]:
            peer_dict = speaker_cfg["peers"][peer]
            if "enable-par" in peer_dict:
                print(peer_dict)
    if "performance-aware" in config:
        print(config["performance-aware"])
