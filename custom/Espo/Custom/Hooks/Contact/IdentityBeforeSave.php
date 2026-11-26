<?php

namespace Espo\Custom\Hooks\Contact;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-IDINT-001: identity integrity for Contact (BeforeSave). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 *
 * @implements BeforeSave<Entity>
 */
class IdentityBeforeSave implements BeforeSave
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $this->guard->beforeSave($entity, $options);
    }
}
