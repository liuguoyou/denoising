from tqdm import tqdm
from utils.loader import TestDataset
from torch.utils.data import DataLoader
from pathlib import Path
import torch
import models
import torch
import torchvision.transforms.functional as F

def test(args, sample_transform):
    model_path = Path(args.run_on_test[0]).resolve()
    if model_path.is_file():
        model_args = torch.load(model_path.parent / "denoising.config")
    elif model_path.is_dir():
        model_args = torch.load(model_path / "denoising.config")
        model_path = model_path / "model_best.pth.tar"
    if len(args.run_on_test) > 2:
        save_path = Path(args.run_on_test[2]).resolve()
    else:
        # Default to saving images alongside the model checkpoint,
        # in a folder by the same name
        save_path = model_path.parent / model_path.name.split(".")[0]

    save_path.mkdir(parents=True)

    print('==> Loading checkpoint for testing')
    checkpoint = torch.load(model_path)
    print('==> Checkpoint loaded')
    model = getattr(models, model_args.model)(args)
    model = model.cuda() if args.cuda else model
    model.load_state_dict(checkpoint['model'])
    model.eval()

    test_dataset = TestDataset(args.run_on_test[1], transform=sample_transform)
    test_loader = DataLoader(test_dataset, num_workers=args.workers, pin_memory=args.cuda)


    with torch.no_grad():
        for img_no, sample in enumerate(tqdm(test_loader)):
            noisy = sample['noisy']
            noisy = noisy.cuda() if args.cuda else noisy
            iso = sample['iso']
            iso = iso.cuda() if args.cuda else iso

            denoised = model(noisy, iso)
            denoised = denoised.cpu()
            im = F.to_pil_image(torch.squeeze(denoised))
            im.save(save_path / f"Test_Image_{img_no+1}.png")
