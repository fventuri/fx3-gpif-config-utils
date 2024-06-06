# FX3 GPIF config utilities

Some utilities in Python to print and modify FX3 GPIF config files generated by Cypress GPIF II designer

- print_gpif_config.py - prints waveform info from a FX3 GPIF config file
- modify_gpif_config_alphas_and_betas.py - modifies waveforms (alphas and betas) in a FX3 GPIF config file (creates a modified copy)


## Examples

Show the waveforms (alphas, betas, and other settings) from a FX3 GPIF config file:
```
print_gpif_config.py cyfxgpif2config.h
```

Show just the alphas and from a FX3 GPIF config file:
```
print_gpif_config.py -a cyfxgpif2config.h
```

Modify the alphas and betas in a FX3 config file:
```
print_gpif_config.py -a cyfxgpif2config.h > alphas_and_betas.txt
# edit the text file alphas_and_betas.txt changing values as needed
modify_gpif_config_alphas_and_betas.py cyfxgpif2config.h < alphas_and_betas.txt
```


## License

Licensed under the GNU GPL V3 (see [LICENSE](LICENSE))
